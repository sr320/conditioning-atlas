#!/usr/bin/env python3
"""
Fallback for assemblies whose NCBI download has no cds_from_genomic.fna
(the Roslin *C. gigas* RefSeq annotation is one): build it from the genome
FASTA + GFF3 so the CpG O/E and isoform-collapse steps see the same header
attributes ([gene=...] [protein_id=...]) as an NCBI CDS file.

Spliced CDS per mRNA, reverse-complemented on the minus strand, phase ignored
(only base composition is used downstream). Writes
genomics/data/<ACC>/cds_from_genomic.fna and, unless --keep-genome, deletes
the genome FASTA afterwards to reclaim disk.

Usage:
    python3 genomics/cds_from_gff.py GCF_902806645.1 [--keep-genome]
"""
import csv
import glob
import os
import re
import sys

from p2common import DATA

COMP = str.maketrans("ACGTacgtNn", "TGCAtgcaNn")


def read_genome(path):
    seqs, name, buf = {}, None, []
    with open(path) as fh:
        for line in fh:
            if line.startswith(">"):
                if name:
                    seqs[name] = "".join(buf)
                name, buf = line[1:].split()[0], []
            else:
                buf.append(line.strip())
    if name:
        seqs[name] = "".join(buf)
    return seqs


def attrs(s):
    return dict(kv.split("=", 1) for kv in s.strip().split(";") if "=" in kv)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    acc = sys.argv[1]
    d = os.path.join(DATA, acc)
    gff = glob.glob(os.path.join(d, "*genomic.gff"))
    fna = [p for p in glob.glob(os.path.join(d, "*genomic.fna")) if "cds_from" not in p]
    if not gff or not fna:
        sys.exit(f"need genomic.gff and genomic.fna in {d}")
    print(f"reading genome {fna[0]} ...", flush=True)
    genome = read_genome(fna[0])
    print(f"  {len(genome)} sequences", flush=True)

    # protein_id -> (seqid, strand, [(start,end)], gene, product)
    cds = {}
    gene_of_rna = {}
    with open(gff[0]) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if len(f) < 9:
                continue
            if f[2] in ("mRNA", "transcript"):
                a = attrs(f[8])
                gene_of_rna[a.get("ID")] = a.get("gene") or a.get("locus_tag") or a.get("Parent", "")
            elif f[2] == "CDS":
                a = attrs(f[8])
                pid = a.get("protein_id")
                if not pid:
                    continue
                rec = cds.setdefault(pid, dict(seqid=f[0], strand=f[6], parts=[], parent=a.get("Parent", ""),
                                               gene=a.get("gene") or a.get("locus_tag", ""), product=a.get("product", "")))
                rec["parts"].append((int(f[3]), int(f[4])))
    out = os.path.join(d, "cds_from_genomic.fna")
    n = 0
    with open(out, "w") as fh:
        for pid, rec in cds.items():
            chrom = genome.get(rec["seqid"])
            if chrom is None:
                continue
            parts = sorted(rec["parts"])
            seq = "".join(chrom[s - 1:e] for s, e in parts)
            if rec["strand"] == "-":
                seq = seq.translate(COMP)[::-1]
            gene = rec["gene"] or gene_of_rna.get(rec["parent"], "") or pid
            loc = f"{'complement(' if rec['strand'] == '-' else ''}{parts[0][0]}..{parts[-1][1]}{')' if rec['strand'] == '-' else ''}"
            fh.write(f">lcl|{rec['seqid']}_cds_{pid} [gene={gene}] [protein={rec['product']}] [protein_id={pid}] [location={loc}] [source=cds_from_gff.py]\n")
            for i in range(0, len(seq), 80):
                fh.write(seq[i:i + 80] + "\n")
            n += 1
    print(f"Wrote {out}: {n} CDS")

    man = os.path.join(DATA, "annotations_manifest.tsv")
    rows = list(csv.reader(open(man, newline=""), delimiter="\t"))
    for r in rows[1:]:
        if r[1] == acc:
            r[4] = out
    with open(man, "w", newline="") as fh:
        csv.writer(fh, delimiter="\t", lineterminator="\n").writerows(rows)
    print("manifest updated")
    if "--keep-genome" not in sys.argv:
        os.remove(fna[0])
        print(f"removed {fna[0]}")


if __name__ == "__main__":
    main()
