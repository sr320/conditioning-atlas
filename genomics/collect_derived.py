#!/usr/bin/env python3
"""
Collect computed genome features into genome_derived.tsv (repository root).

genome_derived.tsv is the record of every value COMPUTED from an assembly, as
opposed to curated from the literature (genome_features.tsv). One row per
species x feature x method, with tool, version, database, accession, date and
evidence. It is generated -- do not hand-edit. Rows are keyed by
(species, feature, method); re-running replaces rows with the same key and
keeps everything else.

Sources this script knows how to ingest:
  --from-ncbi            BUSCO completeness and contig N50 that NCBI reports in
                         its dataset report for each accession in the panel
                         (available for RefSeq-annotated assemblies). Needs
                         network access, no local tools.
  --from-busco DIR       Our own BUSCO runs: DIR/<ACC>/short_summary.*.json,
                         as written by genomics/run_busco.sh.

Later phases append their own ingesters here (machinery calls, CpG O/E,
domain counts, repeat fraction, heterozygosity) so the provenance columns stay
uniform.

Usage:
    python3 genomics/collect_derived.py --from-ncbi
    python3 genomics/collect_derived.py --from-ncbi --from-busco genomics/results/busco
"""
import argparse
import csv
import datetime
import glob
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "genome_derived.tsv")
HDR = ["species", "feature", "value", "method", "tool_version", "database", "accession", "date", "evidence"]
TODAY = datetime.date.today().isoformat()


def load_panel():
    with open(os.path.join(ROOT, "genome_features.tsv"), newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def load_existing():
    if not os.path.exists(OUT):
        return {}
    with open(OUT, newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    return {(r["species"], r["feature"], r["method"]): r for r in rows}


def ncbi_report(acc):
    url = f"https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/{acc}/dataset_report"
    req = urllib.request.Request(url, headers={"accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        reps = json.load(r).get("reports", [])
    return reps[0] if reps else None


def from_ncbi(panel):
    rows = []
    for p in panel:
        acc = p["assembly_accession"]
        if not acc.startswith(("GCA_", "GCF_")):
            continue
        try:
            rep = ncbi_report(acc)
        except Exception as e:  # network hiccup: report and move on
            print(f"  ! {acc}: {e}", file=sys.stderr)
            continue
        if not rep:
            print(f"  ! {acc}: no NCBI report", file=sys.stderr)
            continue
        stats = rep.get("assembly_stats", {})
        if "contig_n50" in stats:
            rows.append(dict(species=p["species"], feature="contig_n50_kb",
                             value=f"{int(stats['contig_n50']) / 1e3:.0f}",
                             method="NCBI assembly report", tool_version="", database="",
                             accession=acc, date=TODAY,
                             evidence=f"assembly_level={rep['assembly_info'].get('assembly_level', '')}; "
                                      f"total_length_mb={int(stats.get('total_sequence_length', 0)) / 1e6:.0f}"))
        b = rep.get("annotation_info", {}).get("busco")
        if b:
            rows.append(dict(species=p["species"], feature="busco_complete_pct",
                             value=f"{float(b['complete']) * 100:.1f}",
                             method="NCBI RefSeq annotation report (proteins)",
                             tool_version=b.get("busco_ver", ""), database=b.get("busco_lineage", ""),
                             accession=acc, date=TODAY,
                             evidence=f"single={float(b.get('single_copy', 0)) * 100:.1f}; "
                                      f"duplicated={float(b.get('duplicated', 0)) * 100:.1f}; "
                                      f"fragmented={float(b.get('fragmented', 0)) * 100:.1f}; "
                                      f"missing={float(b.get('missing', 0)) * 100:.1f}; "
                                      f"total_count={b.get('total_count', '')}"))
        print(f"  {acc}: {'busco ' + rows[-1]['value'] + '%' if b else 'no NCBI busco'}")
    return rows


def from_busco(panel, busco_dir):
    by_acc = {p["assembly_accession"]: p for p in panel}
    rows = []
    for path in sorted(glob.glob(os.path.join(busco_dir, "*", "short_summary.*.json"))):
        acc = os.path.basename(os.path.dirname(path))
        p = by_acc.get(acc)
        if not p:
            print(f"  ! {path}: accession {acc} not in panel", file=sys.stderr)
            continue
        with open(path) as fh:
            js = json.load(fh)
        res, params = js.get("results", {}), js.get("parameters", {})
        mode = params.get("mode", "")
        lineage = js.get("lineage_dataset", {}).get("name", params.get("lineage_dataset", ""))
        rows.append(dict(species=p["species"], feature="busco_complete_pct",
                         value=f"{float(res.get('Complete percentage', res.get('Complete', 0))):.1f}",
                         method=f"BUSCO ({mode} mode)", tool_version=js.get("versions", {}).get("busco", ""),
                         database=lineage, accession=acc, date=TODAY,
                         evidence="; ".join(f"{k}={res[k]}" for k in
                                            ("Single copy", "Multi copy", "Fragmented", "Missing", "n_markers")
                                            if k in res)))
        print(f"  {acc}: busco {rows[-1]['value']}% ({mode})")
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from-ncbi", action="store_true")
    ap.add_argument("--from-busco", metavar="DIR")
    a = ap.parse_args()
    if not (a.from_ncbi or a.from_busco):
        ap.error("nothing to collect; pass --from-ncbi and/or --from-busco DIR")

    panel = load_panel()
    merged = load_existing()
    new = []
    if a.from_ncbi:
        print("NCBI dataset reports:")
        new += from_ncbi(panel)
    if a.from_busco:
        print(f"BUSCO summaries in {a.from_busco}:")
        new += from_busco(panel, a.from_busco)
    for r in new:
        merged[(r["species"], r["feature"], r["method"])] = r

    rows = sorted(merged.values(), key=lambda r: (r["species"], r["feature"], r["method"]))
    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=HDR, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {OUT}: {len(rows)} rows ({len(new)} collected this run)")


if __name__ == "__main__":
    main()
