#!/usr/bin/env python3
"""
Merge the per-sweep extraction files into the single canonical dataset.

Reads:  rows_*.tsv           (27 tab-separated fields each, no header — see SCHEMA.md)
        excluded_*.tsv        (doi<TAB>title<TAB>reason, one screened-out paper per line)
Writes: merged.json           (list of row dicts, includes derived "cluster" field)
        conditioning_atlas.tsv (same data, header row, tab-separated — the canonical flat file)

Run this after adding or editing any rows_*.tsv file. It is safe to re-run —
it always rebuilds merged.json and conditioning_atlas.tsv from scratch from
whatever rows_*.tsv / excluded_*.tsv files are present in this directory.

Usage:
    python3 scripts/merge_rows.py
"""
import csv
import glob
import json
import os

HDR = [
    "study_id", "doi", "pmid", "year", "species", "taxon", "stressor", "stressor_category",
    "conditioning_stage", "dose_treatment", "duration", "generations", "transmission", "challenge",
    "persistence_days", "multiple_timepoints", "decay", "readouts", "direction", "effect_magnitude",
    "molecular_layers", "concordance", "applied_framing", "replication", "evidence_source",
    "editorial_notice", "notes",
]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def cluster_name_from_filename(fname):
    """rows_bivalve_temp_ph.tsv -> a readable cluster label. Extend this map as new
    sweep files are added; unknown filenames fall back to the stem itself."""
    known = {
        "rows_bivalve_temp_ph.tsv": "Bivalve: temperature & pH",
        "rows_coral.tsv": "Coral / cnidarian",
        "rows_immune.tsv": "Immune priming",
        "rows_other.tsv": "Hypoxia / salinity / pollutant / other taxa",
    }
    return known.get(fname, fname.replace("rows_", "").replace(".tsv", ""))


def load_rows():
    rows = []
    for path in sorted(glob.glob(os.path.join(ROOT, "rows_*.tsv"))):
        fname = os.path.basename(path)
        cluster = cluster_name_from_filename(fname)
        with open(path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.rstrip("\n")
                if not line.strip():
                    continue
                parts = line.split("\t")
                if len(parts) != len(HDR):
                    raise ValueError(
                        f"{fname}:{lineno} has {len(parts)} fields, expected {len(HDR)}. "
                        f"Row starts: {parts[0]!r}"
                    )
                d = dict(zip(HDR, [p.strip() for p in parts]))
                d["cluster"] = cluster
                rows.append(d)
    return rows


def dedupe(rows):
    """Warn (do not silently drop) on duplicate DOI+study_id pairs across sweep files.
    A genuine duplicate (same DOI, same study_id) is dropped, keeping the first
    occurrence. Two different experiments from the same paper should have distinct
    study_id suffixes (Lastname_Year, Lastname_Year_b, ...) and are NOT duplicates."""
    seen = set()
    out = []
    dropped = []
    for r in rows:
        key = (r["doi"].lower(), r["study_id"].lower())
        if key in seen:
            dropped.append(r["study_id"])
            continue
        seen.add(key)
        out.append(r)
    if dropped:
        print(f"Dropped {len(dropped)} exact-duplicate row(s): {', '.join(dropped)}")
    return out


def check_study_id_doi_conflicts(rows):
    """Hard error: one study_id must map to exactly one DOI. SCHEMA.md requires
    that two papers from the same first author + year get distinct a/b suffixes
    (Wang_2023a, Wang_2023b). A study_id shared across different DOIs is almost
    always two independent sweeps each minting the bare Lastname_Year id, and it
    silently merges two papers in every downstream table and plot."""
    by_id = {}
    for r in rows:
        by_id.setdefault(r["study_id"].lower(), {}).setdefault(r["doi"].lower(), r)
    conflicts = {k: v for k, v in by_id.items() if len(v) > 1}
    if conflicts:
        lines = []
        for sid, dois in sorted(conflicts.items()):
            lines.append(f"  {next(iter(dois.values()))['study_id']}:")
            for doi, r in dois.items():
                lines.append(f"    {doi}  ({r['species']}; {r['cluster']})")
        raise SystemExit(
            f"ERROR: {len(conflicts)} study_id(s) map to more than one DOI. Give each paper "
            f"its own a/b suffix in the rows_*.tsv source (see SCHEMA.md, field 1):\n"
            + "\n".join(lines)
        )

def check_duplicate_dois(rows):
    """Not an error — a paper can contribute more than one experiment — but print a
    reminder to eyeball these, since it is also the signature of an accidental
    double-extraction across two sweeps."""
    from collections import Counter
    c = Counter(r["doi"].lower() for r in rows if r["doi"] != "not reported")
    dups = {k: v for k, v in c.items() if v > 1}
    if dups:
        print(f"\n{len(dups)} DOI(s) appear in more than one row (expected when a paper "
              f"reports multiple experiments — verify each is a distinct experiment, not a re-extraction):")
        for doi, n in dups.items():
            ids = [r["study_id"] for r in rows if r["doi"].lower() == doi]
            print(f"  {doi}  x{n}  -> {ids}")


def main():
    rows = load_rows()
    print(f"Loaded {len(rows)} rows from rows_*.tsv")
    rows = dedupe(rows)
    check_study_id_doi_conflicts(rows)
    check_duplicate_dois(rows)

    out_json = os.path.join(ROOT, "merged.json")
    with open(out_json, "w") as fh:
        json.dump(rows, fh, indent=0)
    print(f"\nWrote {out_json} ({len(rows)} rows)")

    out_tsv = os.path.join(ROOT, "conditioning_atlas.tsv")
    fieldnames = list(rows[0].keys()) if rows else HDR + ["cluster"]
    with open(out_tsv, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t")
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {out_tsv}")

    n_excluded = 0
    for path in glob.glob(os.path.join(ROOT, "excluded_*.tsv")):
        with open(path) as fh:
            n_excluded += sum(1 for line in fh if line.strip())
    print(f"\n{n_excluded} screened-out papers across excluded_*.tsv files (informational only).")


if __name__ == "__main__":
    main()
