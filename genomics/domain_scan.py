#!/usr/bin/env python3
"""
Phase 2, step 3: hmmsearch the Pfam subset against every proteome in
genomics/data/annotations_manifest.tsv (panel and baseline).

Uses Pfam's own gathering thresholds (--cut_ga) so a hit means "this is a
member of the family by Pfam's curated cutoff", not an arbitrary E-value.
Output: genomics/results/domains/<ACC>.domtblout, skipped if present.

Usage:
    THREADS=4 python3 genomics/domain_scan.py
"""
import os
import subprocess
import sys

from p2common import DB, DOMAINS, load_manifest


def main():
    hmm = os.path.join(DB, "pfam_subset.hmm")
    if not os.path.exists(hmm):
        sys.exit("missing genomics/db/pfam_subset.hmm; run fetch_pfam.py first")
    threads = os.environ.get("THREADS", "4")
    os.makedirs(DOMAINS, exist_ok=True)
    for r in load_manifest():
        out = os.path.join(DOMAINS, r["accession"] + ".domtblout")
        if os.path.exists(out) and os.path.getsize(out) > 0:
            print(f"= {r['accession']} scanned")
            continue
        print(f"+ hmmsearch {r['accession']} ({r['species']}, {r['n_proteins']} proteins)", flush=True)
        subprocess.run(["hmmsearch", "--cut_ga", "--cpu", threads, "--noali",
                        "--domtblout", out + ".tmp", hmm, r["protein_faa"]],
                       check=True, stdout=subprocess.DEVNULL)
        os.replace(out + ".tmp", out)
    print("done")


if __name__ == "__main__":
    main()
