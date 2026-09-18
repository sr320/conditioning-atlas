#!/usr/bin/env python3
"""
Phase 2, step 4c: genome-wide methylation pattern from CpG observed/expected
in coding sequence.

Germline methylation depletes CpG over evolutionary time (methyl-C deaminates
to T), so a gene body that has long been methylated has CpG O/E well below 1
while an unmethylated one sits near 1. Invertebrate "mosaic" genomes therefore
give a BIMODAL O/E distribution across genes (Gavery & Roberts 2010 showed
this for *C. gigas*); a genome with no methylation gives one mode near 1; a
vertebrate-like globally methylated genome is depleted everywhere.

Method
  * One CDS per gene (the longest), length >= 300 bp, from cds_from_genomic.fna.
  * O/E = (n_CpG x L) / (n_C x n_G); values in (0, 2.5) kept.
  * 1- vs 2-component Gaussian mixture, chosen by BIC (dBIC = BIC1 - BIC2).
  * Classification (bimodal = dBIC > 10, both weights >= 0.15, means >= 0.25 apart):
      bimodal, lower mode <= 0.60, upper mode >= 0.75   -> Mosaic gene-body
        (a depleted, long-methylated fraction AND an unmethylated fraction near 1)
      bimodal with upper mode < 0.70, or unimodal mean < 0.60 -> Global
        (every gene depleted; human CDS gives modes ~0.35/0.62)
      unimodal, mean >= 0.80                            -> Low/absent
        (Drosophila CDS gives ~0.88)
      anything else                                     -> not reported (ambiguous)
    Thresholds are stated in the evidence so a reviewer can disagree.
    Calibrated on the baseline species: human -> Global, Drosophila ->
    Low/absent, Lottia and Branchiostoma -> Mosaic gene-body.

Outputs
  genomics/results/phase2/cpg_oe.tsv            (all species, distribution summary)
  genomics/results/phase2/cpg_oe.derived.tsv    (panel: methylation_pattern)

Usage:
    python3 genomics/cpg_oe.py
"""
import os
import warnings

import numpy as np
from sklearn.mixture import GaussianMixture

from p2common import NR, PHASE2, cds_attrs, derived_row, load_manifest, read_fasta, write_tsv

METHOD = "CpG O/E per gene (longest CDS), 1- vs 2-component Gaussian mixture by BIC"
DATABASE = "NCBI CDS FASTA"


def oe_values(cds_fna):
    best = {}  # gene -> (len, seq)
    for pid, desc, seq in read_fasta(cds_fna):
        a = cds_attrs(desc)
        g = a.get("gene") or a.get("locus_tag") or a.get("protein_id") or pid
        if len(seq) >= 300 and (g not in best or len(seq) > best[g][0]):
            best[g] = (len(seq), seq)
    vals = []
    for L, s in best.values():
        s = s.upper()
        c, g, cg = s.count("C"), s.count("G"), s.count("CG")
        if c and g:
            oe = cg * L / (c * g)
            if 0 < oe < 2.5:
                vals.append(oe)
    return np.array(vals)


def classify(v):
    x = v.reshape(-1, 1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        g1 = GaussianMixture(1, random_state=0).fit(x)
        g2 = GaussianMixture(2, random_state=0, n_init=3).fit(x)
    dbic = g1.bic(x) - g2.bic(x)
    m = g2.means_.ravel(); w = g2.weights_.ravel(); order = np.argsort(m)
    m, w = m[order], w[order]
    bimodal = dbic > 10 and w.min() >= 0.15 and (m[1] - m[0]) >= 0.25
    mean = float(v.mean())
    if bimodal and m[0] <= 0.60 and m[1] >= 0.75:
        call = "Mosaic gene-body"
    elif (bimodal and m[1] < 0.70) or (not bimodal and mean < 0.60):
        call = "Global"
    elif not bimodal and mean >= 0.80:
        call = "Low/absent"
    else:
        call = NR
    return call, dict(n=len(v), mean=mean, median=float(np.median(v)), dbic=float(dbic),
                      mode_lo=float(m[0]), w_lo=float(w[0]), mode_hi=float(m[1]), w_hi=float(w[1]), bimodal=bimodal)


def main():
    table, derived = [], []
    for r in load_manifest():
        if not r["cds_fna"]:
            print(f"{r['species']:32} no CDS file")
            continue
        v = oe_values(r["cds_fna"])
        if len(v) < 500:
            print(f"{r['species']:32} too few genes ({len(v)})")
            continue
        call, s = classify(v)
        table.append(dict(species=r["species"], role=r["role"], accession=r["accession"], call=call,
                          **{k: (f"{x:.3f}" if isinstance(x, float) else x) for k, x in s.items()}))
        print(f"{r['species']:32} {r['role']:9} {call:18} n={s['n']:6} mean={s['mean']:.2f} "
              f"modes {s['mode_lo']:.2f}({s['w_lo']:.2f}) / {s['mode_hi']:.2f}({s['w_hi']:.2f}) dBIC={s['dbic']:.0f}")
        if r["role"] == "panel":
            ev = (f"{s['n']} genes; mean O/E {s['mean']:.2f}, median {s['median']:.2f}; 2-component means "
                  f"{s['mode_lo']:.2f} (w {s['w_lo']:.2f}) and {s['mode_hi']:.2f} (w {s['w_hi']:.2f}); dBIC {s['dbic']:.0f}; "
                  f"{'bimodal' if s['bimodal'] else 'unimodal'} by rule (dBIC>10, min weight>=0.15, separation>=0.25)")
            derived.append(derived_row(r["species"], "methylation_pattern", call, METHOD, "scikit-learn GaussianMixture", DATABASE,
                                       r["accession"], ev))
    write_tsv(os.path.join(PHASE2, "cpg_oe.tsv"), table,
              header=["species", "role", "accession", "call", "n", "mean", "median", "dbic", "mode_lo", "w_lo", "mode_hi", "w_hi", "bimodal"])
    write_tsv(os.path.join(PHASE2, "cpg_oe.derived.tsv"), derived)


if __name__ == "__main__":
    main()
