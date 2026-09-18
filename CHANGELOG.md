# Changelog

Format: newest first. One entry per maintenance pass. See README.md § "Updating the
atlas" for what a normal entry should record.

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
