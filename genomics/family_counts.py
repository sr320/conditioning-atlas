#!/usr/bin/env python3
"""
Phase 2, step 4b: stress / immune gene family sizes per proteome and the
`stress_immune_expansion` call.

Method
  * A gene belongs to a family if any of its protein isoforms carries the
    family's Pfam domain at Pfam's gathering threshold (from the domain scan).
    Isoforms collapse to genes via the CDS FASTA headers.
  * Families: HSP70 (PF00012), IAP (BIR, PF00653), TIR (PF01582), NACHT
    (PF05729), SRCR (PF00530), SOD (Sod_Cu + Sod_Fe_C), GPx (PF00255),
    Prx (AhpC-TSA, PF00578), Catalase (PF00199).
  * Baseline = median count per family across genomics/baseline_species.tsv
    (human, Drosophila, Lottia, Branchiostoma). Ratio = species / baseline.
  * Call: Expanded if >= 2 families have ratio >= 2; Contracted if >= 2
    families have ratio <= 0.5 and none >= 2; otherwise Baseline. Only made
    when the assembly passes the BUSCO gate; counts are still recorded.

Outputs
  genomics/results/phase2/family_counts.tsv          (all species x families, for review)
  genomics/results/phase2/family_counts.derived.tsv  (panel: stress_immune_expansion, hsp70_count, iap_count)

Usage:
    python3 genomics/family_counts.py
"""
import os
import statistics

from p2common import (BUSCO_GATE, DOMAINS, NR, PHASE2, busco_pct, derived_row, hmmer_version, load_manifest,
                      protein_to_gene, read_domtblout, write_tsv)

FAMILIES = {
    "HSP70": {"HSP70"}, "IAP": {"BIR"}, "TIR": {"TIR"}, "NACHT": {"NACHT"}, "SRCR": {"SRCR"},
    "SOD": {"Sod_Cu", "Sod_Fe_C"}, "GPx": {"GSHPx"}, "Prx": {"AhpC-TSA"}, "Catalase": {"Catalase"},
}
METHOD = "Pfam domain presence per gene (hmmsearch --cut_ga), isoforms collapsed via CDS headers; ratio to baseline median"
DATABASE = "Pfam subset via InterPro; baseline = H. sapiens, D. melanogaster, L. gigantea, B. floridae"


def count_species(r):
    dom = os.path.join(DOMAINS, r["accession"] + ".domtblout")
    if not os.path.exists(dom):
        return None
    hits = read_domtblout(dom)
    p2g = protein_to_gene(r["cds_fna"]) if r["cds_fna"] else {}
    genes = {fam: set() for fam in FAMILIES}
    for pid, hs in hits.items():
        names = {h["name"] for h in hs}
        g = p2g.get(pid, pid)
        for fam, doms in FAMILIES.items():
            if names & doms:
                genes[fam].add(g)
    return {fam: len(s) for fam, s in genes.items()}


def main():
    ver = hmmer_version()
    counts, table = {}, []
    for r in load_manifest():
        c = count_species(r)
        if c is None:
            continue
        counts[r["species"]] = (r, c)
        table.append(dict(species=r["species"], role=r["role"], accession=r["accession"],
                          isoform_collapse="yes" if r["cds_fna"] else "NO (protein ids used)", **c))
    base = {fam: statistics.median(c[fam] for sp, (r, c) in counts.items() if r["role"] == "baseline")
            for fam in FAMILIES}
    print("baseline medians:", base)

    derived = []
    for sp, (r, c) in counts.items():
        if r["role"] != "panel":
            continue
        ratios = {fam: (c[fam] / base[fam] if base[fam] else float("inf")) for fam in FAMILIES}
        up = [f for f, x in ratios.items() if x >= 2]
        down = [f for f, x in ratios.items() if x <= 0.5]
        call = "Expanded" if len(up) >= 2 else "Contracted" if len(down) >= 2 and not up else "Baseline"
        gate = busco_pct(sp)
        gated = gate is not None and gate >= BUSCO_GATE
        ev = "; ".join(f"{fam} {c[fam]} (x{ratios[fam]:.1f} vs {base[fam]:.0f})" for fam in FAMILIES)
        if not r["cds_fna"]:
            ev += "; WARNING isoforms not collapsed"
        ev += f"; BUSCO {'unknown' if gate is None else f'{gate:.1f}%'}"
        derived.append(derived_row(sp, "stress_immune_expansion", call if gated else NR, METHOD, ver, DATABASE, r["accession"],
                                   ev + ("" if gated else "; gate not met, call withheld (would be " + call + ")")))
        derived.append(derived_row(sp, "hsp70_count", c["HSP70"], METHOD, ver, DATABASE, r["accession"],
                                   f"genes with HSP70 domain; x{ratios['HSP70']:.1f} vs baseline median {base['HSP70']:.0f}"))
        derived.append(derived_row(sp, "iap_count", c["IAP"], METHOD, ver, DATABASE, r["accession"],
                                   f"genes with BIR domain; x{ratios['IAP']:.1f} vs baseline median {base['IAP']:.0f}"))
        print(f"{sp:32} {call:10} {'(gated)' if gated else '(withheld)':10} " + " ".join(f"{f}={c[f]}" for f in FAMILIES))
    for sp, (r, c) in counts.items():
        if r["role"] == "baseline":
            print(f"{sp:32} baseline              " + " ".join(f"{f}={c[f]}" for f in FAMILIES))

    write_tsv(os.path.join(PHASE2, "family_counts.tsv"), table,
              header=["species", "role", "accession", "isoform_collapse"] + list(FAMILIES))
    write_tsv(os.path.join(PHASE2, "family_counts.derived.tsv"), derived)


if __name__ == "__main__":
    main()
