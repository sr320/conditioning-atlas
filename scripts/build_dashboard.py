#!/usr/bin/env python3
"""
Build the standalone and GitHub Pages dashboards from merged.json +
dashboard_template.html.

dashboard_template.html is the real source file (edit charts, filters, or styling
there). This script only:
  1. derives the two fields the dashboard's JS needs beyond what's in merged.json
     (`p`: persistence_days parsed to a float or None; `approx`: whether the
     source value started with '~'),
  2. injects that data and a footer string into the __DATA__ / __FOOT__
     placeholders in the template,
  3. writes the self-contained result to Conditioning_Atlas_dashboard.html and
     docs/index.html.

Never hand-edit Conditioning_Atlas_dashboard.html or docs/index.html directly —
they are generated and will be overwritten the next time this script runs.

Usage:
    python3 scripts/build_dashboard.py
"""
import datetime
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def pnum(s):
    s = s.strip()
    if "not reported" in s.lower():
        return None
    m = re.search(r"-?\d+\.?\d*", s.replace(",", ""))
    return float(m.group()) if m else None


def main():
    with open(os.path.join(ROOT, "merged.json")) as fh:
        rows = json.load(fh)

    for r in rows:
        r["p"] = pnum(r["persistence_days"])
        r["approx"] = r["persistence_days"].strip().startswith("~")

    data_json = json.dumps(rows, separators=(",", ":"))

    npap = len(set(r["doi"].lower() for r in rows if r["doi"] != "not reported"))
    foot = (
        "Assembled from PubMed, Consensus, and Scite full-text retrieval. Every DOI was resolved through Scite "
        "and checked for retractions, corrections, and expressions of concern; no editorial notices were found on "
        "any included paper at time of extraction. A verification pass then re-checked a sample of rows "
        "line-by-line against full text; see the repository CHANGELOG for what that pass corrected. "
        "Inclusion required a marine or estuarine invertebrate, a deliberate sublethal conditioning exposure "
        "applied before a later assessment, a later-life or offspring outcome, and a primary empirical design. "
        "Rows sourced from abstracts alone are marked as such in the workbook and should be checked against the "
        "full text before citation. Extraction was automated and screened against explicit criteria, but this is "
        "not a registered systematic review — no PRISMA flow, no dual independent extraction, no formal "
        "risk-of-bias assessment. Treat it as a working lab resource and the scaffold for a real review. "
        f"{len(rows)} experiments · {npap} papers · built {datetime.date.today().isoformat()}."
    )
    last_run = os.path.join(ROOT, "sweep_state", "last_run.json")
    if os.path.exists(last_run):
        with open(last_run) as fh:
            through = json.load(fh)["until"]
        foot += (f" New literature screened through {through} by the weekly automated sweep; screened "
                 "papers awaiting extraction are listed in the repository's pending_review.tsv.")

    tpl_path = os.path.join(ROOT, "dashboard_template.html")
    with open(tpl_path) as fh:
        tpl = fh.read()

    html = tpl.replace("__DATA__", data_json).replace("__FOOT__", json.dumps(foot))

    out_paths = [
        os.path.join(ROOT, "Conditioning_Atlas_dashboard.html"),
        os.path.join(ROOT, "docs", "index.html"),
    ]
    os.makedirs(os.path.dirname(out_paths[1]), exist_ok=True)
    for out_path in out_paths:
        with open(out_path, "w") as fh:
            fh.write(html)
        print(f"Wrote {out_path} ({len(html) / 1024:.1f} KB, {len(rows)} rows)")


if __name__ == "__main__":
    main()
