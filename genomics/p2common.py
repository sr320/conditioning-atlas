"""Shared helpers for the phase 2 scripts (domain scan, machinery calls, family
counts, CpG O/E). Stdlib only."""
import csv
import datetime
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(HERE, "data")
DB = os.path.join(HERE, "db")
RESULTS = os.path.join(HERE, "results")
DOMAINS = os.path.join(RESULTS, "domains")
PHASE2 = os.path.join(RESULTS, "phase2")
HDR = ["species", "feature", "value", "method", "tool_version", "database", "accession", "date", "evidence"]
TODAY = datetime.date.today().isoformat()
NR = "not reported"
BUSCO_GATE = 90.0


def load_manifest(role=None):
    path = os.path.join(DATA, "annotations_manifest.tsv")
    with open(path, newline="") as fh:
        rows = [r for r in csv.DictReader(fh, delimiter="\t") if r["protein_faa"]]
    return [r for r in rows if role is None or r["role"] == role]


def hmmer_version():
    try:
        out = subprocess.run(["hmmsearch", "-h"], capture_output=True, text=True).stdout
        m = re.search(r"HMMER (\S+)", out)
        return m.group(1) if m else "hmmer"
    except OSError:
        return "hmmer"


def read_fasta(path):
    """Yield (id, description, sequence) for each record."""
    pid, desc, seq = None, "", []
    with open(path) as fh:
        for line in fh:
            if line.startswith(">"):
                if pid is not None:
                    yield pid, desc, "".join(seq)
                head = line[1:].strip()
                pid, _, desc = head.partition(" ")
                seq = []
            else:
                seq.append(line.strip())
    if pid is not None:
        yield pid, desc, "".join(seq)


_ATTR = re.compile(r"\[(\w+)=([^\]]*)\]")


def cds_attrs(desc):
    return dict(_ATTR.findall(desc))


def protein_to_gene(cds_fna):
    """protein_id -> gene symbol / locus tag, from NCBI cds_from_genomic.fna headers."""
    m = {}
    with open(cds_fna) as fh:
        for line in fh:
            if line.startswith(">"):
                a = cds_attrs(line)
                pid = a.get("protein_id")
                if pid:
                    m[pid] = a.get("gene") or a.get("locus_tag") or pid
    return m


def read_domtblout(path):
    """protein_id -> list of dicts (one per domain hit)."""
    hits = {}
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.split()
            if len(f) < 22:
                continue
            hits.setdefault(f[0], []).append(dict(
                name=f[3], acc=f[4].split(".")[0], qlen=int(f[5]), tlen=int(f[2]),
                ievalue=float(f[12]), score=float(f[13]),
                hmm_from=int(f[15]), hmm_to=int(f[16]), ali_from=int(f[17]), ali_to=int(f[18])))
    return hits


def busco_pct(species):
    """Best known BUSCO completeness for a panel species from genome_derived.tsv, or None."""
    path = os.path.join(ROOT, "genome_derived.tsv")
    if not os.path.exists(path):
        return None
    best = None
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            if r["species"] == species and r["feature"] == "busco_complete_pct":
                try:
                    v = float(r["value"])
                    best = v if best is None else max(best, v)
                except ValueError:
                    pass
    return best


def derived_row(species, feature, value, method, tool_version, database, accession, evidence):
    return dict(species=species, feature=feature, value=str(value), method=method, tool_version=tool_version,
                database=database, accession=accession, date=TODAY, evidence=evidence)


def write_tsv(path, rows, header=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    header = header or HDR
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=header, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {path} ({len(rows)} rows)")
