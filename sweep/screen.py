#!/usr/bin/env python3
"""Step 3 of the weekly sweep: screen candidates against the inclusion criteria.

Reads sweep_runs/<run_id>/candidates.jsonl, asks Claude for a structured
decision per paper, and writes decisions.jsonl and screen_usage.json.

    python -m sweep.screen --run-id 2026-W48              # Message Batches (weekly default, 50% cheaper)
    python -m sweep.screen --run-id backtest --direct     # concurrent direct calls, for quick iteration
    python -m sweep.screen --run-id backtest --precedent-ref fc079b3^

The system prompt (sweep/prompts/screen_system.md) is filled with precedents
from the atlas itself: one line per included experiment and every recorded
exclusion reason. A backtest passes --precedent-ref so the precedents come
from before the sweep being reproduced and the answers are not in the prompt.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import sys
import time

import anthropic

from sweep.common import ROOT, RUNS, _ls, _read, norm_doi, read_jsonl, write_jsonl

MODEL = "claude-opus-5-5"
EFFORT = "low"

YNU = {"type": "string", "enum": ["yes", "no", "unclear"]}
SCHEMA = {
    "type": "object",
    "properties": {
        "marine_invertebrate": YNU,
        "priming_exposure": YNU,
        "later_outcome": YNU,
        "primary_empirical": YNU,
        "decision": {"type": "string", "enum": ["include", "exclude", "needs_full_text", "preprint_hold"]},
        "cluster": {"type": "string", "enum": ["bivalve_temp_ph", "coral", "immune", "other"]},
        "reason": {"type": "string"},
    },
    "required": ["marine_invertebrate", "priming_exposure", "later_outcome", "primary_empirical",
                 "decision", "cluster", "reason"],
    "additionalProperties": False,
}


def build_system(ref: str | None) -> str:
    included, excluded = [], []
    for name in _ls("rows_*.tsv", ref):
        for line in _read(name, ref).splitlines():
            f = line.split("\t")
            if len(f) >= 19:
                # study_id | species | stressor | stage | challenge | direction
                included.append(f"- {f[0]} | {f[4]} | {f[6]} | stage: {f[8]} | later: {f[13]} | {f[18]}")
    for name in _ls("excluded_*.tsv", ref):
        for line in _read(name, ref).splitlines():
            f = line.split("\t")
            if len(f) >= 3 and norm_doi(f[0]):
                excluded.append(f"- {f[1][:150]} — {f[2][:300]}")
    tmpl = (ROOT / "sweep" / "prompts" / "screen_system.md").read_text(encoding="utf-8")
    return tmpl.replace("{included}", "\n".join(included)).replace("{excluded}", "\n".join(excluded))


def user_message(c: dict) -> str:
    kind = "preprint" if c.get("is_preprint") or c["doi"].startswith(("10.1101/", "10.64898/", "10.21203/")) \
        else "journal article"
    return (f"Title: {c['title']}\n"
            f"Journal: {c.get('journal') or 'unknown'} ({kind}, {c.get('year') or 'year unknown'})\n"
            f"DOI: {c['doi'] or 'none'}\n\n"
            f"Abstract: {c['abstract'] or '(no abstract available)'}")


def params(system: str, c: dict) -> dict:
    return {
        "model": MODEL,
        "max_tokens": 4000,
        "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral", "ttl": "1h"}}],
        "output_config": {"effort": EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}},
        "messages": [{"role": "user", "content": user_message(c)}],
    }


def parse(msg, c: dict) -> dict:
    base = {"doi": c["doi"], "title": c["title"]}
    if msg.stop_reason == "refusal":
        cat = getattr(msg.stop_details, "category", None) if msg.stop_details else None
        return {**base, "decision": "needs_full_text", "cluster": "other",
                "reason": f"model declined to screen (refusal, category {cat}); screen by hand", "refused": True}
    text = next((b.text for b in msg.content if b.type == "text"), "")
    try:
        return {**base, **json.loads(text)}
    except json.JSONDecodeError:
        return {**base, "decision": "needs_full_text", "cluster": "other",
                "reason": f"unparseable model output (stop_reason {msg.stop_reason}); screen by hand"}


def add_usage(tot: dict, u) -> None:
    for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
        tot[k] = tot.get(k, 0) + (getattr(u, k, 0) or 0)


def run_direct(client, system, cands, workers):
    usage, out = {}, {}

    def one(i_c):
        i, c = i_c
        p = params(system, c)
        # Server-side fallback: if a safety classifier declines (e.g. a pathogen
        # paper), the same request is retried on a fallback model in this call.
        msg = client.beta.messages.create(**p, betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        return i, msg

    # Warm the cache with one request before fanning out.
    i0, m0 = one((0, cands[0]))
    out[i0] = parse(m0, cands[0]); add_usage(usage, m0.usage)
    with cf.ThreadPoolExecutor(workers) as ex:
        for n, (i, msg) in enumerate(ex.map(one, list(enumerate(cands))[1:]), 2):
            out[i] = parse(msg, cands[i]); add_usage(usage, msg.usage)
            if n % 25 == 0:
                print(f"  screened {n}/{len(cands)}", file=sys.stderr)
    return [out[i] for i in range(len(cands))], usage, {"mode": "direct"}


def run_batch(client, system, cands, poll):
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request
    reqs = [Request(custom_id=f"c{i:05d}", params=MessageCreateParamsNonStreaming(**params(system, c)))
            for i, c in enumerate(cands)]
    batch = client.messages.batches.create(requests=reqs)
    print(f"  batch {batch.id} submitted ({len(reqs)} requests)", file=sys.stderr)
    while (b := client.messages.batches.retrieve(batch.id)).processing_status != "ended":
        print(f"  {b.processing_status}: {b.request_counts.processing} processing", file=sys.stderr)
        time.sleep(poll)
    usage, out = {}, {}
    for r in client.messages.batches.results(batch.id):
        i = int(r.custom_id[1:])
        if r.result.type == "succeeded":
            out[i] = parse(r.result.message, cands[i]); add_usage(usage, r.result.message.usage)
        else:
            out[i] = {"doi": cands[i]["doi"], "title": cands[i]["title"], "decision": "needs_full_text",
                      "cluster": "other", "reason": f"batch request {r.result.type}; screen by hand"}
    return [out[i] for i in range(len(cands))], usage, {"mode": "batch", "batch_id": batch.id}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--direct", action="store_true", help="concurrent direct calls instead of a batch")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--poll", type=int, default=60)
    ap.add_argument("--precedent-ref", default=None)
    ap.add_argument("--limit", type=int, default=0, help="screen only the first N (testing)")
    ap.add_argument("--rescreen", action="store_true", help="ignore decisions already in this run")
    a = ap.parse_args()

    run = RUNS / a.run_id
    cands = read_jsonl(run / "candidates.jsonl")
    if a.limit:
        cands = cands[:a.limit]
    if not cands:
        print("no candidates"); return
    system = build_system(a.precedent_ref)
    (run / "screen_system_prompt.md").write_text(system, encoding="utf-8")

    # Re-running a step (after a discovery fix, say) only pays for papers not yet screened.
    prior = {}
    if (run / "decisions.jsonl").exists() and not a.rescreen:
        prior = {(d["doi"], d["title"]): d for d in read_jsonl(run / "decisions.jsonl")}
    todo = [c for c in cands if (c["doi"], c["title"]) not in prior]
    print(f"  {len(cands) - len(todo)} reused from earlier decisions, {len(todo)} to screen", file=sys.stderr)

    decs_new, usage, meta = [], {}, {"mode": "none"}
    if todo:
        client = anthropic.Anthropic()
        decs_new, usage, meta = (run_direct(client, system, todo, a.workers) if a.direct
                                 else run_batch(client, system, todo, a.poll))
    new = {(d["doi"], d["title"]): d for d in decs_new}
    decs = [new.get((c["doi"], c["title"])) or prior[(c["doi"], c["title"])] for c in cands]
    write_jsonl(run / "decisions.jsonl", decs)
    meta.update(model=MODEL, effort=EFFORT, n=len(cands), screened_now=len(todo), usage=usage)
    (run / "screen_usage.json").write_text(json.dumps(meta, indent=2) + "\n")
    counts = {}
    for d in decs:
        counts[d["decision"]] = counts.get(d["decision"], 0) + 1
    print(json.dumps({"decisions": counts, **meta}, indent=2))


if __name__ == "__main__":
    main()
