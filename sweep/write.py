#!/usr/bin/env python3
"""Record a run's screening decisions in the atlas's own files (phase 1).

Phase 1 of WEEKLY_SWEEP_PLAN.md stops before extraction, so nothing is
added to rows_*.tsv. Instead:

  exclude          -> excluded_<cluster>.tsv   (doi, title, reason)
  include          -> pending_review.tsv       hold_reason "Screened include, needs extraction"
  needs_full_text  -> pending_review.tsv       hold_reason "Needs full text or scope call"
  preprint_hold    -> pending_review.tsv       hold_reason "Preprint"

Every screened paper is also written to sweep_state/seen.tsv so it is never
screened twice, and the run is summarised in sweep_state/last_run.json, a
drafted CHANGELOG.md entry, and sweep_runs/<run_id>/pr_body.md.

    python -m sweep.write --run-id 2026-W47

Exits 0 having written nothing when the run screened no papers.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from collections import Counter

from sweep.common import ROOT, RUNS, STATE, known_dois, read_jsonl, record_key

HOLD = {
    "include": "Screened include, needs extraction",
    "needs_full_text": "Needs full text or scope call",
    "preprint_hold": "Preprint",
}
PENDING_COLS = ["hold_reason", "doi", "year", "first_author", "title", "species", "stressor", "decision_needed"]
SEEN_COLS = ["key", "doi", "title", "first_seen", "decision", "run_id"]


def cell(s) -> str:
    """One TSV field: no tabs or newlines."""
    return " ".join(str(s or "").split())


def append_tsv(path, rows: list[list[str]], header: list[str] | None = None) -> None:
    new = not path.exists() or path.stat().st_size == 0
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    with path.open("a", encoding="utf-8", newline="") as fh:
        if text and not text.endswith("\n"):
            fh.write("\n")
        if new and header:
            fh.write("\t".join(header) + "\n")
        for r in rows:
            fh.write("\t".join(cell(x) for x in r) + "\n")


def changelog_entry(run_id: str, meta: dict, counts: Counter, by_file: Counter, held: list[dict]) -> str:
    today = dt.date.today().isoformat()
    lines = [
        f"## {today} — Weekly sweep {run_id} (automated screening)",
        "",
        f"- Searched Europe PMC, PubMed and OpenAlex for {meta['since']} to {meta['until']}"
        f" with `sweep/queries.yaml`; {meta['candidates']} papers were new to the atlas"
        f" and screened by `{meta['model']}` (effort `{meta['effort']}`) against the four"
        f" inclusion criteria. Decisions: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) + ".",
        "- **No rows were added.** Phase 1 of `WEEKLY_SWEEP_PLAN.md` stops before extraction:"
        f" {counts.get('include', 0)} screened includes are in `pending_review.tsv` as"
        " \"Screened include, needs extraction\", next to the full-text and preprint holds.",
    ]
    if by_file:
        lines.append("- Screened-out papers appended to " +
                     ", ".join(f"`{f}` ({n})" for f, n in sorted(by_file.items())) + ", with the model's reason.")
    lines += [
        "- Every decision was made from the title and abstract by a model, not a person. Check the"
        " includes and holds before extracting, and skim the exclusions in the PR.",
        "",
    ]
    return "\n".join(lines) + "\n"


def insert_changelog(entry: str) -> None:
    path = ROOT / "CHANGELOG.md"
    text = path.read_text(encoding="utf-8")
    i = text.find("\n## ")
    path.write_text(text[:i + 1] + entry + text[i + 1:] if i >= 0 else text + "\n" + entry,
                    encoding="utf-8")


def pr_body(run_id: str, meta: dict, counts: Counter, kept: list[dict], excluded: list[dict]) -> str:
    out = [
        f"Automated weekly literature sweep **{run_id}** ({meta['since']} to {meta['until']}).",
        "",
        f"{meta['candidates']} papers were new to the atlas and were screened from title and abstract by "
        f"`{meta['model']}`: " + ", ".join(f"**{v}** {k}" for k, v in sorted(counts.items())) + ".",
        "",
        "This is phase 1 of `WEEKLY_SWEEP_PLAN.md`, so no atlas rows are added. Screened includes and"
        " holds go to `pending_review.tsv`, exclusions go to `excluded_*.tsv`, and every screened DOI goes"
        " to `sweep_state/seen.tsv`.",
        "",
        "**To review:**",
        "",
        "- Check the papers below that the model kept.",
        "- Skim the exclusions.",
        "- Fix any decision you disagree with by moving the line between files in this PR.",
        "- Merge.",
        "",
    ]
    if kept:
        out += ["## Kept for a person to look at", "", "| decision | paper | species | why |", "|---|---|---|---|"]
        order = {"include": 0, "needs_full_text": 1, "preprint_hold": 2}
        for d in sorted(kept, key=lambda d: order[d["decision"]]):
            link = f"[{cell(d['title'])[:110]}](https://doi.org/{d['doi']})" if d["doi"] else cell(d["title"])[:110]
            out.append(f"| `{d['decision']}` | {link} | {cell(d.get('species'))} | "
                       f"{cell(d['reason']).replace('|', '/')} |")
        out.append("")
    if excluded:
        out += ["<details><summary>Excluded ({})</summary>".format(len(excluded)), ""]
        for d in excluded:
            link = f"[{cell(d['title'])[:110]}](https://doi.org/{d['doi']})" if d["doi"] else cell(d["title"])[:110]
            out.append(f"- {link} — {cell(d['reason'])}")
        out += ["", "</details>", ""]
    u = meta.get("usage") or {}
    out += [f"<sub>Tokens: {u.get('input_tokens', 0):,} input, {u.get('cache_read_input_tokens', 0):,} cached,"
            f" {u.get('output_tokens', 0):,} output. Run files: `sweep_runs/{run_id}/`.</sub>", "",
            "🤖 Generated with [Claude Code](https://claude.com/claude-code)", ""]
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", required=True)
    a = ap.parse_args()
    run = RUNS / a.run_id

    if not (run / "decisions.jsonl").exists():
        print("no decisions in this run; nothing to write")
        return
    cands = {record_key(c): c for c in read_jsonl(run / "candidates.jsonl")}
    decs = read_jsonl(run / "decisions.jsonl")
    disc = json.loads((run / "discover_summary.json").read_text())
    scr = json.loads((run / "screen_usage.json").read_text())
    meta = {"since": disc["since"], "until": disc["until"], "candidates": len(decs),
            "model": scr.get("model"), "effort": scr.get("effort"), "usage": scr.get("usage")}

    # A paper recorded since discovery ran (a hand edit, a concurrent PR) is skipped, not duplicated.
    known = known_dois()
    today = dt.date.today().isoformat()
    excl_rows: dict[str, list] = {}
    pend_rows, seen_rows, kept, excluded = [], [], [], []
    counts, by_file = Counter(), Counter()
    for d in decs:
        c = cands.get(record_key(d), {})
        key = record_key(d)
        if key in known:
            continue
        counts[d["decision"]] += 1
        seen_rows.append([key, d["doi"], d["title"], today, d["decision"], a.run_id])
        if d["decision"] == "exclude":
            excluded.append(d)
            if d["doi"]:  # excluded_*.tsv is keyed by DOI; no-DOI exclusions live in seen.tsv only
                f = f"excluded_{d['cluster']}.tsv"
                excl_rows.setdefault(f, []).append([d["doi"], d["title"], d["reason"]])
                by_file[f] += 1
        else:
            kept.append(d)
            pend_rows.append([HOLD[d["decision"]], d["doi"] or "not reported", c.get("year", ""),
                              c.get("first_author", ""), d["title"], d.get("species", "not reported"),
                              d.get("stressor", "not reported"),
                              f"Automated screen {a.run_id}: {d['reason']}"])

    if not seen_rows:
        print("every screened paper is already recorded; nothing to write")
        return
    for f, rows in excl_rows.items():
        append_tsv(ROOT / f, rows)
    if pend_rows:
        append_tsv(ROOT / "pending_review.tsv", pend_rows, PENDING_COLS)
    append_tsv(STATE / "seen.tsv", seen_rows, SEEN_COLS)
    (STATE / "last_run.json").write_text(json.dumps({
        "run_id": a.run_id, "date": today, "since": meta["since"], "until": meta["until"],
        "screened": sum(counts.values()), "decisions": dict(counts), "model": meta["model"]}, indent=2) + "\n")
    insert_changelog(changelog_entry(a.run_id, meta, counts, by_file, kept))
    (run / "pr_body.md").write_text(pr_body(a.run_id, meta, counts, kept, excluded), encoding="utf-8")
    print(json.dumps({"written": dict(counts), "excluded_files": dict(by_file)}, indent=2))


if __name__ == "__main__":
    main()
