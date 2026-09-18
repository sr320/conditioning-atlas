#!/usr/bin/env python3
"""
Phase 2, step 4a: DNA methylation machinery calls (dnmt1, dnmt3, tet) per
proteome.

Method
  1. Candidates = proteins carrying the C-5 methylase domain (DNA_methylase,
     PF00145) or the TET/JBP oxygenase domain (Tet_JBP, PF12851), from the
     --cut_ga domain scan.
  2. Each candidate is assigned to its best-scoring human reference by phmmer
     against genomics/db/reference_machinery.faa (DNMT1, DNMT3A/B/L, TRDMT1,
     TET1/2/3). The domain architecture on the same protein (BAH / DNMT1-RFD
     for DNMT1, PWWP / ADD for DNMT3) is recorded as corroborating evidence.
     DNMT2/TRDMT1, the tRNA methyltransferase, is the classic false positive
     for "DNMT present" and is reported separately.
  3. Isoforms are collapsed to genes via the CDS FASTA headers.
  4. Present  = at least one gene assigned to the class.
     Absent   = no candidate AND the assembly passes the BUSCO gate (>= 90 %).
                Even then the call is proteome-only: a gene missing from the
                annotation is not a gene missing from the genome. The
                evidence field says "assembly-level search pending".
     not reported = no candidate and the gate is unknown or not met.

Outputs
  genomics/results/phase2/machinery.derived.tsv  (panel species, derived format)
  genomics/results/phase2/machinery_all.tsv      (panel + baseline, one line per gene, for review)

Usage:
    python3 genomics/machinery_calls.py
"""
import os
import subprocess
import tempfile

from p2common import (BUSCO_GATE, DB, DOMAINS, NR, PHASE2, busco_pct, derived_row, hmmer_version,
                      load_manifest, protein_to_gene, read_domtblout, read_fasta, write_tsv)

METHOD = "Pfam domain architecture + phmmer best hit vs human references (proteome only)"
DATABASE = "Pfam subset via InterPro; UniProt DNMT1/DNMT3A/B/L/TRDMT1/TET1/2/3"
CLASS_OF = {"DNMT1": "dnmt1", "DNMT3A": "dnmt3", "DNMT3B": "dnmt3", "DNMT3L": "dnmt3",
            "TET1": "tet", "TET2": "tet", "TET3": "tet", "TRDMT1": "dnmt2"}
ARCH_DOMAINS = {"BAH", "DNMT1-RFD", "PWWP", "ADD_DNMT3", "DNA_methylase", "Tet_JBP"}


def best_refs(cand_seqs):
    """phmmer candidates vs references -> {protein_id: (ref_label, evalue)}"""
    if not cand_seqs:
        return {}
    with tempfile.TemporaryDirectory() as td:
        q = os.path.join(td, "cand.faa")
        with open(q, "w") as fh:
            for pid, seq in cand_seqs.items():
                fh.write(f">{pid}\n{seq}\n")
        tbl = os.path.join(td, "hits.tbl")
        subprocess.run(["phmmer", "--noali", "--tblout", tbl, q, os.path.join(DB, "reference_machinery.faa")],
                       check=True, stdout=subprocess.DEVNULL)
        best = {}
        with open(tbl) as fh:
            for line in fh:
                if line.startswith("#"):
                    continue
                f = line.split()
                target, query, ev = f[0], f[2], float(f[4])
                if ev < 1e-10 and (query not in best or ev < best[query][1]):
                    best[query] = (target, ev)
    return best


def call_species(r, ver):
    acc = r["accession"]
    dom_path = os.path.join(DOMAINS, acc + ".domtblout")
    if not os.path.exists(dom_path):
        return [], []
    hits = read_domtblout(dom_path)
    p2g = protein_to_gene(r["cds_fna"]) if r["cds_fna"] else {}
    cands = {pid: hs for pid, hs in hits.items() if any(h["name"] in ("DNA_methylase", "Tet_JBP") for h in hs)}
    seqs = {pid: s for pid, _, s in read_fasta(r["protein_faa"]) if pid in cands}
    refs = best_refs(seqs)

    genes = {}  # gene -> dict(cls, ref, arch, pids, plen)
    for pid, hs in cands.items():
        ref, ev = refs.get(pid, ("none", None))
        cls = CLASS_OF.get(ref, "unassigned")
        arch = "+".join(sorted({h["name"] for h in hs if h["name"] in ARCH_DOMAINS}))
        gene = p2g.get(pid, pid)
        g = genes.setdefault(gene, dict(cls=set(), ref=set(), arch=set(), pids=[], plen=0))
        g["cls"].add(cls); g["ref"].add(ref); g["arch"].add(arch); g["pids"].append(pid)
        g["plen"] = max(g["plen"], len(seqs.get(pid, "")))

    review = [dict(species=r["species"], role=r["role"], accession=acc, gene=g, classes="/".join(sorted(d["cls"])),
                   best_ref="/".join(sorted(d["ref"])), architecture="|".join(sorted(d["arch"])),
                   max_protein_len=d["plen"], n_isoforms=len(d["pids"]), protein_ids=";".join(d["pids"][:4]))
              for g, d in sorted(genes.items())]

    derived = []
    if r["role"] != "panel":
        return derived, review
    gate = busco_pct(r["species"])
    for feature in ("dnmt1", "dnmt3", "tet"):
        found = [(g, d) for g, d in genes.items() if feature in d["cls"]]
        if found:
            ev = "; ".join(f"{g} [{'|'.join(sorted(d['arch']))}; best {'/'.join(sorted(d['ref']))}; {d['plen']} aa]"
                           for g, d in found[:6])
            value = "Present"
        else:
            other = ", ".join(f"{g} ({'/'.join(sorted(d['cls']))})" for g, d in genes.items()) or "none"
            if gate is not None and gate >= BUSCO_GATE:
                value = "Absent"
                ev = f"no {feature.upper()} candidate in proteome (BUSCO {gate:.1f}% passes gate); assembly-level search pending; other methylase/TET genes: {other}"
            else:
                value = NR
                ev = f"no {feature.upper()} candidate in proteome; BUSCO gate {'unknown' if gate is None else f'{gate:.1f}% < {BUSCO_GATE:.0f}%'} so absence not callable; other: {other}"
        derived.append(derived_row(r["species"], feature, value, METHOD, ver, DATABASE, acc, ev))
    dnmt2 = [g for g, d in genes.items() if "dnmt2" in d["cls"]]
    derived.append(derived_row(r["species"], "dnmt2_trdmt1_genes", len(dnmt2), METHOD, ver, DATABASE, acc,
                               "; ".join(dnmt2) or "none (tRNA methyltransferase, reported for completeness; not scored)"))
    return derived, review


def main():
    ver = hmmer_version()
    derived, review = [], []
    for r in load_manifest():
        d, rv = call_species(r, ver)
        derived += d; review += rv
        calls = {x["feature"]: x["value"] for x in d}
        print(f"{r['species']:32} {r['role']:9} " + (" ".join(f"{k}={calls[k]}" for k in ("dnmt1", "dnmt3", "tet") if k in calls) or
              " | ".join(f"{x['gene']}:{x['classes']}" for x in rv) or "no candidates"))
    write_tsv(os.path.join(PHASE2, "machinery.derived.tsv"), derived)
    write_tsv(os.path.join(PHASE2, "machinery_all.tsv"), review,
              header=["species", "role", "accession", "gene", "classes", "best_ref", "architecture",
                      "max_protein_len", "n_isoforms", "protein_ids"])


if __name__ == "__main__":
    main()
