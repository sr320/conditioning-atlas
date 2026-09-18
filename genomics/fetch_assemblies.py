#!/usr/bin/env python3
"""
Phase 1, step 1: download every assembly that has an NCBI accession in
genome_features.tsv, using the NCBI Datasets CLI, and write a manifest that the
later steps read.

For each accession this fetches the genome FASTA, the protein FASTA and GFF3
where NCBI has an annotation, and the sequence report, into
genomics/data/<ACC>/. Existing downloads are skipped.

Output: genomics/data/manifest.tsv with one row per species:
    species, accession, genome_fasta, protein_fasta, gff, proteome_url, notes
`protein_fasta` is empty when NCBI has no annotation; `proteome_url` is a
hand-filled override for gene models hosted elsewhere (left empty here; the
manifest is regenerated on every run, so keep overrides in
genomics/proteome_overrides.tsv — species<TAB>url — and they are merged in).

Usage:
    python3 genomics/fetch_assemblies.py [--dry-run]
"""
import csv
import glob
import os
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(HERE, "data")
NR = "not reported"


def sh(cmd, dry):
    print("+", " ".join(cmd), flush=True)
    if not dry:
        subprocess.run(cmd, check=True)


def find_one(pattern):
    hits = sorted(glob.glob(pattern, recursive=True))
    return hits[0] if hits else ""


def main():
    dry = "--dry-run" in sys.argv
    if not dry and shutil.which("datasets") is None:
        sys.exit("ERROR: the NCBI `datasets` CLI is not on PATH; create the conda env in genomics/environment.yml")

    with open(os.path.join(ROOT, "genome_features.tsv"), newline="") as fh:
        panel = list(csv.DictReader(fh, delimiter="\t"))

    overrides = {}
    ov_path = os.path.join(HERE, "proteome_overrides.tsv")
    if os.path.exists(ov_path):
        with open(ov_path, newline="") as fh:
            for line in csv.reader(fh, delimiter="\t"):
                if len(line) >= 2 and not line[0].startswith("#"):
                    overrides[line[0].strip()] = line[1].strip()

    os.makedirs(DATA, exist_ok=True)
    manifest = []
    for r in panel:
        acc = r["assembly_accession"]
        if not acc.startswith(("GCA_", "GCF_")):
            manifest.append([r["species"], "", "", "", "", overrides.get(r["species"], ""), "no NCBI accession"])
            continue
        out_dir = os.path.join(DATA, acc)
        zip_path = os.path.join(DATA, acc + ".zip")
        if not os.path.isdir(out_dir):
            sh(["datasets", "download", "genome", "accession", acc,
                "--include", "genome,protein,gff3,seq-report",
                "--filename", zip_path], dry)
            if not dry:
                with zipfile.ZipFile(zip_path) as z:
                    z.extractall(out_dir)
                os.remove(zip_path)
        else:
            print(f"= {acc} already downloaded", flush=True)
        genome = find_one(os.path.join(out_dir, "**", f"{acc}*_genomic.fna"))
        protein = find_one(os.path.join(out_dir, "**", "protein.faa"))
        gff = find_one(os.path.join(out_dir, "**", "genomic.gff"))
        note = "" if protein else "no NCBI annotation; proteome needs an override or ab initio prediction before phase 2"
        manifest.append([r["species"], acc, genome, protein, gff, overrides.get(r["species"], ""), note])

    man_path = os.path.join(DATA, "manifest.tsv")
    with open(man_path, "w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["species", "accession", "genome_fasta", "protein_fasta", "gff", "proteome_url", "notes"])
        w.writerows(manifest)
    n_acc = sum(1 for m in manifest if m[1])
    n_prot = sum(1 for m in manifest if m[3])
    print(f"\nWrote {man_path}: {len(manifest)} species, {n_acc} with assemblies, {n_prot} with NCBI proteomes")


if __name__ == "__main__":
    main()
