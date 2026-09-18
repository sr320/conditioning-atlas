#!/usr/bin/env python3
"""
Phase 2, step 2: build the HMM and reference-protein databases.

  * Pfam profiles listed in genomics/pfam_profiles.tsv, fetched one at a time
    from the InterPro API and concatenated into genomics/db/pfam_subset.hmm
    (then hmmpress'd). Only the ~16 families the rubric needs, so no full
    Pfam-A download.
  * Human reference proteins for the methylation machinery from UniProt, into
    genomics/db/reference_machinery.faa, used to assign DNMT candidates to
    DNMT1 / DNMT3 / TRDMT1 and TET candidates to TET by best phmmer hit.

Existing files are reused. Usage:
    python3 genomics/fetch_pfam.py
"""
import csv
import gzip
import io
import os
import shutil
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "db")
INTERPRO = "https://www.ebi.ac.uk/interpro/wwwapi/entry/pfam/{acc}?annotation=hmm"
UNIPROT = "https://rest.uniprot.org/uniprotkb/{acc}.fasta"

# UniProt accession -> label used in calls
REFS = {
    "P26358": "DNMT1", "Q9Y6K1": "DNMT3A", "Q9UBC3": "DNMT3B", "Q9UJW3": "DNMT3L",
    "O14717": "TRDMT1", "Q8NFU7": "TET1", "Q6N021": "TET2", "O43151": "TET3",
}


def fetch(url, binary=False):
    req = urllib.request.Request(url, headers={"accept": "*/*", "user-agent": "conditioning-atlas/0.1"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    return data if binary else data.decode()


def main():
    os.makedirs(DB, exist_ok=True)
    hmm_path = os.path.join(DB, "pfam_subset.hmm")
    if not os.path.exists(hmm_path):
        parts, missing = [], []
        with open(os.path.join(HERE, "pfam_profiles.tsv"), newline="") as fh:
            for r in csv.DictReader(fh, delimiter="\t"):
                try:
                    raw = fetch(INTERPRO.format(acc=r["accession"]), binary=True)
                    try:
                        txt = gzip.GzipFile(fileobj=io.BytesIO(raw)).read().decode()
                    except OSError:
                        txt = raw.decode()
                    if not txt.startswith("HMMER3"):
                        raise ValueError("response is not an HMMER3 profile")
                    parts.append(txt if txt.endswith("\n") else txt + "\n")
                    print(f"  {r['accession']} {r['name']}: ok")
                except Exception as e:
                    missing.append(r["accession"])
                    print(f"  ! {r['accession']} {r['name']}: {e}", file=sys.stderr)
        if missing:
            print(f"WARNING: {len(missing)} profiles missing: {missing}", file=sys.stderr)
        with open(hmm_path, "w") as fh:
            fh.write("".join(parts))
        for ext in ("h3f", "h3i", "h3m", "h3p"):
            p = hmm_path + "." + ext
            if os.path.exists(p):
                os.remove(p)
        if shutil.which("hmmpress"):
            subprocess.run(["hmmpress", hmm_path], check=True, stdout=subprocess.DEVNULL)
        print(f"Wrote {hmm_path} ({len(parts)} profiles)")
    else:
        print(f"= {hmm_path} exists")

    ref_path = os.path.join(DB, "reference_machinery.faa")
    if not os.path.exists(ref_path):
        out = []
        for acc, label in REFS.items():
            try:
                fa = fetch(UNIPROT.format(acc=acc))
                lines = fa.strip().split("\n")
                out.append(f">{label} {lines[0][1:]}\n" + "\n".join(lines[1:]) + "\n")
                print(f"  {acc} {label}: ok")
            except Exception as e:
                print(f"  ! {acc} {label}: {e}", file=sys.stderr)
        with open(ref_path, "w") as fh:
            fh.write("".join(out))
        print(f"Wrote {ref_path} ({len(out)} references)")
    else:
        print(f"= {ref_path} exists")


if __name__ == "__main__":
    main()
