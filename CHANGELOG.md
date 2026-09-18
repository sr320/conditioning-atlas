# Changelog

Format: newest first. One entry per maintenance pass. See README.md § "Updating the
atlas" for what a normal entry should record.

## 2026-09-17 — Split two study_ids that each covered two papers

- Two `study_id`s were shared by two different papers each, violating the
  `SCHEMA.md` rule that rows from the same first author and year with different
  papers take an `a`/`b` suffix. Each pair had been minted independently in two
  sweeps as the bare `Lastname_Year`, so the dashboard, workbook, and any
  per-study grouping silently merged two unrelated experiments. Suffixes were
  assigned in publication order (earlier PMID = `a`):
  - `Wang_2023` → `Wang_2023a` (10.1016/j.scitotenv.2023.162112, *Crassostrea
    gigas*, natural intertidal environment; `rows_bivalve_temp_ph.tsv`) and
    `Wang_2023b` (10.1016/j.dci.2023.105122, *C. gigas*, formalin-inactivated
    *Vibrio alginolyticus*; `rows_immune.tsv`).
  - `Zhao_2024` → `Zhao_2024a` (10.1016/j.scitotenv.2024.173585, *Tigriopus
    japonicus*, nickel and ocean acidification; `rows_other.tsv`) and
    `Zhao_2024b` (10.3390/ijms252313174, *Eriocheir sinensis*, *Aeromonas
    hydrophila*; `rows_immune.tsv`).
  - Confirmed no `Wang_2023a/b` or `Zhao_2024a/b` already existed, and no
    other row's `notes` referenced the old ids. Row content is unchanged; only
    field 1 differs. Still 109 experiments from 105 papers.
- `scripts/merge_rows.py` now fails (exit 1) when one `study_id` maps to more
  than one DOI, printing each offending id with its DOIs, species, and sweep
  file. The existing same-DOI / different-`study_id` reminder is unchanged
  since that pattern is legitimate (one paper, several experiments).
  Documented in README.md § "Adding a new paper".
- Regenerated `merged.json`, `conditioning_atlas.tsv`, `Conditioning_Atlas.xlsx`,
  `Conditioning_Atlas_dashboard.html`, and `docs/index.html`.

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
