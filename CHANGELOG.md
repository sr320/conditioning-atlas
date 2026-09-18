# Changelog

Format: newest first. One entry per maintenance pass. See README.md § "Updating the
atlas" for what a normal entry should record.

## 2026-09-17 — Genome pipeline, phase 1 (accessions and quality gate)

- Goal: replace taxon-level imputation on the Priming likelihood page with
  values computed from the public assemblies. 133 of 154 scored genome cells
  in the 22-species panel were `not reported`. Plan and provenance rule are in
  `genomics/README.md`; computed values will be a third class (curated over
  computed over imputed) recorded in `genome_derived.tsv`, never written into
  `genome_features.tsv`.
- Resolved NCBI accessions for 9 of the 10 species that lacked one, preferring
  RefSeq-annotated, then chromosome-level, then the NCBI representative
  assembly: *R. philippinarum* GCA_964294305.1, *O. lurida* GCA_061099505.1,
  *P. fucata* GCA_028142955.1, *A. hyacinthus* GCA_964291705.1,
  *S. pistillata* GCF_002571385.2 (RefSeq proteome; a 2026 chromosome-level
  GCA exists), *M. capitata* GCA_949126865.1 (size corrected from the 2019
  draft's 886 Mb to 689 Mb), *T. japonicus* GCA_010645155.1, *P. lividus*
  GCA_984792215.1, *B. neritina* GCA_964035545.1. *O. labronica* has no NCBI
  assembly. Assembly level and size in `genome_features.tsv` now follow the
  chosen accession, with the accession added to `sources`.
- New `genomics/` directory: conda environment, `fetch_assemblies.py`
  (NCBI Datasets download + manifest), `run_busco.sh` (metazoa_odb10, proteins
  mode where a proteome exists), `collect_derived.py` (ingests NCBI-reported
  BUSCO and our own runs into `genome_derived.tsv`). Downloads and results are
  git-ignored; BUSCO runs on the lab server, not locally or in CI.
- `genome_derived.tsv` seeded from NCBI dataset reports: contig N50 for all 21
  accessioned species and BUSCO completeness for the six RefSeq-annotated
  assemblies (93.5–99.3%, per-clade lineages, so not yet comparable with our
  uniform metazoa_odb10 runs).
- Decisions recorded: computed values will feed the score directly, shown with
  a distinct basis; heterozygosity thresholds will be set after GenomeScope
  values for the oysters are in hand.

## 2026-09-17 — Priming likelihood page

- New page, `docs/priming-likelihood.html` (also `Priming_Likelihood.html`),
  linked from the dashboard header. It ranks a curated species panel by a
  transparent, adjustable rubric for the relative likelihood of a favourable
  priming response, from genome features (DNA methylation machinery,
  genome-wide methylation pattern, stress/immune gene family expansion,
  repeat fraction, heterozygosity) and life-history modifiers (habitat
  variability, reproductive mode, larval mode, generation time,
  photosymbiosis). Output is rank and tier relative to the panel; the numeric
  score is behind the breakdown. Assembly level and annotation are shown as a
  tractability badge and not scored.
- New source files: `genome_features.tsv` (22 species, header row, `sources`
  column; schema in `GENOME_SCHEMA.md`) and `priming_model.json` (default
  weights, scoring rules, rationale, sources). New build step
  `scripts/build_predictor.py`, which validates both files, matches panel
  species to atlas rows by name including the atlas's synonym spellings
  (`Magallana gigas`, `Penaeus vannamei`, `Exaiptasia diaphana`), and injects
  panel, atlas, and rubric into `predictor_template.html`. CI now runs it and
  checks both page copies.
- Panel curation notes. All 30 cited DOIs were resolved through Crossref and
  13 NCBI accessions were checked against the NCBI Datasets API for organism,
  assembly level, and size before inclusion. Values not stated in a cited
  source were left `not reported` rather than filled from memory or from a
  congener: e.g. *Tigriopus japonicus* carries no methylation-machinery
  values even though *T. californicus* (included as a comparator, not in the
  atlas) has lost DNMT1 and DNMT3; coral DNMT/TET presence is left for
  curation from Liew et al. 2018; *S. purpuratus* methylation pattern is left
  unreported pending a WGBS source. The validator refused two rows of the
  first draft (assembly claims without a source) and those fields were set to
  `not reported` rather than sourced after the fact.
- Atlas coverage: 21 of 22 panel species have atlas rows; 77 of 109 atlas
  experiments match a panel species. The 32 unmatched rows are mostly
  single-experiment coral, crustacean, and echinoderm species that can be
  added to the panel as their genomes are curated.
- Not done: no default weight has been fitted to anything. The page's anchor
  check (Spearman ρ between rubric score and the atlas *Improved* fraction
  across species with ≥2 assessable experiments) is a plausibility display,
  not validation, and should be read that way.

## 2026-08-04 — Initial build

- First extraction sweep: 4 parallel literature pulls (bivalve temperature/pH,
  coral/cnidarian, immune priming, hypoxia/salinity/pollutant/other-taxa) against
  PubMed, Consensus, and Scite. 110 raw rows, 131 screened-out papers.
- Merged and deduplicated to 109 experiments from 105 papers (one exact duplicate
  dropped: `Donelan_2023` had been independently pulled into two sweeps).
- Verification pass: 6 high-leverage rows re-checked line-by-line against full
  text. Found and fixed:
  - `Drury_2022` — `effect_magnitude` quoted an ANOVA statistic (F=2.498, p=0.042)
    that the source paper itself attributes to initial pre-ramp Fv/Fm and explicitly
    discounts as driven by a single pairwise comparison. Replaced with the actual
    ED10 comparisons that support the paper's claim, and softened an internally
    false superlative in `notes` ("longest persistence in this set") that was
    contradicted by four other rows in the same file.
  - `Klepac_2020b` — `direction` was coded `No effect`; the source reports a
    significant chlorophyll decline in transplanted vs. native colonies, so this
    was revised to `Mixed`.
  - `Lafont_2017a` — `challenge` contained an unresolved `10^n` placeholder (a
    superscript exponent lost when PMC full text was converted to plain text).
    Replaced with an explicit note that the titre needs the original PDF rather
    than shipping a fabricated number.
  - Added a `PERSISTENCE SEMANTICS` caveat to `notes` on `Klepac_2020a`,
    `Klepac_2020b`, and `Uthicke_2024`: these rows report an exposure/tracking
    window under continuous or repeated conditioning, not a post-conditioning
    recovery gap, and should not be ranked against clean-gap rows like
    `Drury_2022` or `Lafont_2017a`.
  - Confirmed (not changed): the counterintuitive `Klepac_2020a` finding — the
    *most* thermally variable source pool producing the *most* bleaching-susceptible
    corals — is correctly transcribed, not inverted. Confirmed `Parker_2015`'s
    ~426-day persistence value is derived from the paper's own 14-month
    common-garden period. Confirmed no `persistence_days` value over 365 is a
    weeks-recorded-as-days unit error.
- Built `Conditioning_Atlas.xlsx` (5 sheets: README, Atlas, Coverage gaps, Data
  dictionary, Screened out) and `Conditioning_Atlas_dashboard.html` (filterable,
  6 filters, coverage heatmap, persistence strip plot).
- Reconstructed the ad hoc build steps into `scripts/merge_rows.py`,
  `scripts/build_xlsx.py`, `scripts/recalc_xlsx.py`, `scripts/build_dashboard.py`
  so the pipeline is re-runnable rather than one-off.
