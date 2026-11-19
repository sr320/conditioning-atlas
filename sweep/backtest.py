#!/usr/bin/env python3
"""Score a sweep run against a past manual sweep.

The ground truth is what a sweep commit added: DOIs appended to rows_*.tsv
are `include`, to excluded_*.tsv are `exclude`, and to pending_review.tsv are
`hold` (preprints and undecided papers). The default commit is the October
2026 manual sweep, fc079b3.

    python -m sweep.backtest --run-id backtest-2026-10            # discovery + screening
    python -m sweep.backtest --run-id backtest-2026-10 --stage discover

Writes sweep_runs/<run_id>/backtest.md and backtest.json.
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
from collections import Counter

from sweep.common import RUNS, ROOT, norm_doi, read_jsonl


def added_lines(commit: str, path_glob: str) -> list[tuple[str, str]]:
    out = subprocess.run(["git", "diff", "--unified=0", f"{commit}^", commit, "--", path_glob],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    lines, cur = [], ""
    for ln in out.splitlines():
        if ln.startswith("+++ b/"):
            cur = ln[6:]
        elif ln.startswith("+") and not ln.startswith("+++"):
            lines.append((cur, ln[1:]))
    return lines


def ground_truth(commit: str) -> dict[str, dict]:
    truth: dict[str, dict] = {}
    for f, ln in added_lines(commit, "rows_*.tsv"):
        p = ln.split("\t")
        truth.setdefault(norm_doi(p[1]), {"label": "include", "file": f, "id": p[0], "title": p[6][:90]})
    for f, ln in added_lines(commit, "excluded_*.tsv"):
        p = ln.split("\t")
        truth.setdefault(norm_doi(p[0]), {"label": "exclude", "file": f, "id": "", "title": p[1][:90],
                                          "reason": p[2] if len(p) > 2 else ""})
    pend = [ln for _, ln in added_lines(commit, "pending_review.tsv")]
    for row in csv.DictReader(pend, delimiter="\t"):
        d = norm_doi(row.get("doi"))
        if d:
            truth.setdefault(d, {"label": "hold", "file": "pending_review.tsv", "id": row.get("first_author", ""),
                                 "title": (row.get("title") or "")[:90],
                                 "hold_reason": row.get("hold_reason", "")})
    truth.pop("", None)
    return truth


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--commit", default="fc079b3")
    ap.add_argument("--stage", choices=["discover", "screen"], default="screen")
    a = ap.parse_args()
    run = RUNS / a.run_id

    truth = ground_truth(a.commit)
    hits = {h["doi"]: h for h in read_jsonl(run / "hits.jsonl") if h["doi"]}
    cands = {h["doi"]: h for h in read_jsonl(run / "candidates.jsonl") if h["doi"]}
    dec = {}
    if a.stage == "screen" and (run / "decisions.jsonl").exists():
        dec = {d["doi"]: d for d in read_jsonl(run / "decisions.jsonl")}

    by_label = Counter(t["label"] for t in truth.values())
    res = {"truth": dict(by_label), "found": Counter(), "candidate": Counter()}
    rows = []
    for doi, t in sorted(truth.items(), key=lambda kv: (kv[1]["label"], kv[0])):
        h = hits.get(doi)
        found = h is not None
        cand = doi in cands
        res["found"][t["label"]] += found
        res["candidate"][t["label"]] += cand
        why = "" if cand else ("not returned by any source" if not found else
                               "dropped by local prefilter" if not h["prefilter"] else f"known ({h['known_in']})")
        d = dec.get(doi, {})
        rows.append({"doi": doi, **t, "found": found, "candidate": cand, "miss_reason": why,
                     "sources": ",".join(h["sources"]) if h else "",
                     "decision": d.get("decision", ""), "model_reason": d.get("reason", "")})

    md = [f"# Backtest `{a.run_id}` vs manual sweep {a.commit}", ""]
    md.append("## Discovery recall")
    md.append("")
    md.append("| truth label | n | returned by a source | reached screening |")
    md.append("|---|---|---|---|")
    for lab in ("include", "hold", "exclude"):
        n = by_label.get(lab, 0)
        md.append(f"| {lab} | {n} | {res['found'][lab]} ({res['found'][lab] / max(n, 1):.0%}) "
                  f"| {res['candidate'][lab]} ({res['candidate'][lab] / max(n, 1):.0%}) |")
    md.append("")
    extra = [c for c in cands if c not in truth]
    md.append(f"Candidates not in the manual sweep at all: **{len(extra)}** "
              f"(the manual sweep never saw them; screening decides whether they were misses).")

    if dec:
        md += ["", "## Screening vs manual decision", ""]
        cm = Counter((r["label"], r["decision"] or "—") for r in rows if r["candidate"])
        labs = ["include", "needs_full_text", "preprint_hold", "exclude"]
        md.append("| manual \\ model | " + " | ".join(labs) + " |")
        md.append("|---|" + "---|" * len(labs))
        for lab in ("include", "hold", "exclude"):
            md.append(f"| {lab} | " + " | ".join(str(cm.get((lab, m), 0)) for m in labs) + " |")
        inc = [r for r in rows if r["label"] == "include"]
        kept = sum(1 for r in inc if r["decision"] in ("include", "needs_full_text", "preprint_hold"))
        res["include_recall_end_to_end"] = kept / max(len(inc), 1)
        md += ["", f"**End-to-end recall of included papers** (found, and not excluded by the model): "
               f"{kept}/{len(inc)} = {kept / max(len(inc), 1):.0%}", ""]
        new_dec = Counter(dec[c]["decision"] for c in extra if c in dec)
        md.append(f"Model decisions on the {len(extra)} papers the manual sweep never saw: "
                  + ", ".join(f"{k} {v}" for k, v in sorted(new_dec.items())))
        md += ["", "### Papers the model kept that the manual sweep never saw", ""]
        for c in extra:
            if dec.get(c, {}).get("decision") in ("include", "needs_full_text", "preprint_hold"):
                h = cands[c]
                md.append(f"- `{dec[c]['decision']}` [{h['title'][:100]}](https://doi.org/{c}) — {dec[c]['reason']}")
        md += ["", "### Disagreements on papers both saw", ""]
        for r in rows:
            if not r["candidate"]:
                continue
            m = r["decision"]
            agree = (r["label"] == "include" and m == "include") or (r["label"] == "exclude" and m == "exclude") \
                or (r["label"] == "hold" and m in ("needs_full_text", "preprint_hold"))
            if not agree:
                md.append(f"- manual **{r['label']}** / model **{m or '—'}**: "
                          f"[{r['title']}](https://doi.org/{r['doi']}) — model: {r['model_reason']}")

    md += ["", "## Ground-truth papers that never reached screening", ""]
    for r in rows:
        if not r["candidate"]:
            md.append(f"- **{r['label']}** {r['id']} [{r['title']}](https://doi.org/{r['doi']}) — {r['miss_reason']}")

    (run / "backtest.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    res = {k: dict(v) if isinstance(v, Counter) else v for k, v in res.items()}
    (run / "backtest.json").write_text(json.dumps({"summary": res, "rows": rows}, indent=2) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
