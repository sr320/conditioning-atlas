#!/usr/bin/env python3
"""
Phase 2, step 1: fetch protein and CDS FASTA for every annotated assembly via
the NCBI Datasets REST API (no CLI needed, works on a laptop).

Covers the panel (genome_features.tsv) and the baseline species
(genomics/baseline_species.tsv). Assemblies with no NCBI annotation yield no
protein.faa and are recorded as such. Existing files are skipped.

The CDS FASTA headers carry [gene=...] / [locus_tag=...] and [protein_id=...],
which is how later steps collapse protein isoforms to genes without a GFF.

Output:
  genomics/data/<ACC>/protein.faa, cds_from_genomic.fna
  genomics/data/annotations_manifest.tsv:
      species, accession, role, protein_faa, cds_fna, n_proteins

Usage:
    python3 genomics/fetch_annotations.py [--panel-only] [--baseline-only]
"""
import csv
import glob
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(HERE, "data")
API = "https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/{acc}/download" \
      "?include_annotation_type=PROT_FASTA&include_annotation_type=CDS_FASTA&hydrated=FULLY_HYDRATED"


def download(acc, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False, dir=DATA) as tmp:
        tmp_path = tmp.name
    req = urllib.request.Request(API.format(acc=acc), headers={"accept": "application/zip"})
    with urllib.request.urlopen(req, timeout=600) as r, open(tmp_path, "wb") as fh:
        shutil.copyfileobj(r, fh, length=1 << 20)
    with zipfile.ZipFile(tmp_path) as z:
        for member in z.namelist():
            base = os.path.basename(member)
            # some RefSeq packages name the CDS file <ACC>_<asm>_cds_from_genomic.fna
            target = "protein.faa" if base == "protein.faa" else \
                     "cds_from_genomic.fna" if base.endswith("cds_from_genomic.fna") else None
            if target:
                with z.open(member) as src, open(os.path.join(out_dir, target), "wb") as dst:
                    shutil.copyfileobj(src, dst, length=1 << 20)
    os.remove(tmp_path)


def count_fasta(path):
    n = 0
    with open(path) as fh:
        for line in fh:
            if line.startswith(">"):
                n += 1
    return n


def main():
    panel_only = "--panel-only" in sys.argv
    baseline_only = "--baseline-only" in sys.argv
    targets = []
    if not baseline_only:
        with open(os.path.join(ROOT, "genome_features.tsv"), newline="") as fh:
            for r in csv.DictReader(fh, delimiter="\t"):
                targets.append((r["species"], r["assembly_accession"], "panel"))
    if not panel_only:
        with open(os.path.join(HERE, "baseline_species.tsv"), newline="") as fh:
            for r in csv.DictReader(fh, delimiter="\t"):
                targets.append((r["species"], r["accession"], "baseline"))

    os.makedirs(DATA, exist_ok=True)
    manifest = []
    for species, acc, role in targets:
        if not acc.startswith(("GCA_", "GCF_")):
            manifest.append([species, "", role, "", "", "0"])
            continue
        out_dir = os.path.join(DATA, acc)
        prot = os.path.join(out_dir, "protein.faa")
        cds = os.path.join(out_dir, "cds_from_genomic.fna")
        marker = os.path.join(out_dir, ".fetched_annotations")
        if not os.path.exists(marker):
            print(f"+ fetching {acc} ({species})", flush=True)
            try:
                download(acc, out_dir)
                open(marker, "w").close()
            except Exception as e:
                print(f"  ! {acc}: {e}", file=sys.stderr)
        else:
            print(f"= {acc} already fetched", flush=True)
        has_prot = os.path.exists(prot) and os.path.getsize(prot) > 0
        has_cds = os.path.exists(cds) and os.path.getsize(cds) > 0
        n = count_fasta(prot) if has_prot else 0
        manifest.append([species, acc, role, prot if has_prot else "", cds if has_cds else "", str(n)])
        print(f"  {acc}: {n} proteins{'' if has_cds else ', no CDS'}" if has_prot else f"  {acc}: no NCBI annotation")

    out = os.path.join(DATA, "annotations_manifest.tsv")
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["species", "accession", "role", "protein_faa", "cds_fna", "n_proteins"])
        w.writerows(manifest)
    print(f"\nWrote {out}: {sum(1 for m in manifest if m[3])} of {len(manifest)} with proteomes")


if __name__ == "__main__":
    main()
