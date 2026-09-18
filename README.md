# The Conditioning Atlas

[![Validate and build](https://github.com/sr320/conditioning-atlas/actions/workflows/validate.yml/badge.svg)](https://github.com/sr320/conditioning-atlas/actions/workflows/validate.yml)

Priming windows, doses, and persistence of induced environmental memory in
marine invertebrates. A structured, filterable extraction of the sublethal
environmental-conditioning / parental-priming literature — one row per
experiment, not per paper — built for the Roberts Lab's environmental memory
/ predictive phenotyping framework.

This project is maintained in the
[sr320/conditioning-atlas](https://github.com/sr320/conditioning-atlas)
GitHub repository. The
[interactive dashboard](https://sr320.github.io/conditioning-atlas/) is
published through GitHub Pages from `docs/index.html`.

## What's here

| File | What it is | Edit by hand? |
|---|---|---|
| `SCHEMA.md` | The 27-column extraction schema, inclusion criteria, and field-by-field instructions. The contract every row must satisfy. | Yes — this is the spec |
| `rows_*.tsv` | Raw extracted rows, one file per literature sweep, 27 tab-separated fields, no header. **This is the actual source of truth.** | Yes — this is where new studies get added |
| `excluded_*.tsv` | Papers that were screened and rejected, with a one-line reason. Kept so screening is auditable and isn't repeated. | Yes |
| `merged.json` | All `rows_*.tsv` combined, deduplicated, as a JSON list. | **No — generated** by `scripts/merge_rows.py` |
| `conditioning_atlas.tsv` | Same data as `merged.json`, flat TSV with header. The single-file hand-off format. | **No — generated** |
| `Conditioning_Atlas.xlsx` | The lab-facing deliverable: Atlas sheet + live Coverage-gaps formulas + data dictionary + screened-out log. | **No — generated** |
| `dashboard_template.html` | The dashboard's actual HTML/CSS/JS, with `__DATA__` / `__FOOT__` placeholders. | Yes — this is where chart/filter/layout changes go |
| `Conditioning_Atlas_dashboard.html` | `dashboard_template.html` with data injected. Self-contained, opens in any browser. | **No — generated** |
| `docs/index.html` | GitHub Pages copy of the self-contained dashboard. Configure Pages to deploy from the `main` branch's `/docs` folder. | **No — generated** |
| `GENOME_SCHEMA.md` | The 26-column schema for the species panel behind the Priming likelihood page: allowed values, sourcing rules, and how the rubric uses each field. | Yes — this is the spec |
| `genome_features.tsv` | Hand-curated genome and life-history features, one row per species, with a header row and a `sources` column. **Source of truth for the Priming likelihood page.** | Yes — this is where species get added or corrected |
| `priming_model.json` | The Priming likelihood rubric: default weights, scoring rules, rationale, and sources per feature. Data, not code, so the model can be argued with in a pull request. | Yes |
| `predictor_template.html` | The Priming likelihood page's HTML/CSS/JS, with `__PANEL__` / `__ATLAS__` / `__MODEL__` / `__FOOT__` placeholders. | Yes — this is where layout changes go |
| `Priming_Likelihood.html` | `predictor_template.html` with panel, atlas, and rubric injected. Self-contained. | **No — generated** |
| `docs/priming-likelihood.html` | GitHub Pages copy of the Priming likelihood page, linked from the dashboard header. | **No — generated** |
| `CHANGELOG.md` | One entry per maintenance pass: what was added, what was corrected, and why. | Yes — append, don't rewrite history |
| `LICENSE` | Creative Commons Attribution 4.0 International license covering this repository. | No — legal text |
| `scripts/` | The five-step build pipeline (below). | Yes |

The rule of thumb: if a file's row above says "generated," don't hand-edit it —
your edit will be silently overwritten the next time someone runs the
pipeline. Fix the *source* (a `rows_*.tsv` line, or `dashboard_template.html`)
and regenerate.

## The pipeline

```
rows_*.tsv  ──┐
              ├──▶ scripts/merge_rows.py ──▶ merged.json, conditioning_atlas.tsv
excluded_*.tsv┘                                    │
                                                    ├──▶ scripts/build_xlsx.py ──▶ Conditioning_Atlas.xlsx
                                                    │        └──▶ scripts/recalc_xlsx.py (computes the formula sheet)
                                                    │
                                                    ├──▶ scripts/build_dashboard.py ──▶ Conditioning_Atlas_dashboard.html
                                                    │         (combines with dashboard_template.html)
                                                    │         └──▶ docs/index.html (GitHub Pages)
                                                    │
genome_features.tsv ┐                               │
priming_model.json  ├──▶ scripts/build_predictor.py ◀┘ ──▶ Priming_Likelihood.html
                    │         (combines with predictor_template.html)
                    │         └──▶ docs/priming-likelihood.html (GitHub Pages)
```

Run the whole thing after any change to `rows_*.tsv`, `excluded_*.tsv`,
`genome_features.tsv`, or `priming_model.json`:

```bash
python3 scripts/merge_rows.py
python3 scripts/build_xlsx.py
python3 scripts/recalc_xlsx.py Conditioning_Atlas.xlsx
python3 scripts/build_dashboard.py
python3 scripts/build_predictor.py
```

Create a virtual environment and install the Python dependency before running
the pipeline:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The recalculation step also needs LibreOffice (`soffice`/`libreoffice` on
`PATH`). Without it, the workbook still opens fine, but the "Coverage gaps"
sheet's formulas will not show cached values until you open and save the file
once in Excel or LibreOffice.

## Updating the atlas

### Adding new studies (the common case)

1. Find the right `rows_*.tsv` file for the study's taxon/stressor (or start a
   new `rows_<topic>.tsv` if it's a genuinely new category — `merge_rows.py`
   picks up any `rows_*.tsv` file automatically; add its display name to the
   `cluster_name_from_filename()` map in `scripts/merge_rows.py` and the
   `labels` dict in `scripts/build_xlsx.py` so it gets a readable cluster/sweep
   label instead of falling back to the filename stem).
2. Re-read `SCHEMA.md` before extracting — the 27 fields, their allowed
   values, and the "never infer, `not reported` is a finding" rule are not
   optional. Pull full text where possible; abstracts routinely omit exposure
   duration and the persistence window, the two fields the whole atlas exists
   to capture.
3. Append one tab-separated line per **experiment** (a paper testing two
   stressors, or two species, is two rows — use an `a`/`b` suffix on the
   study_id, same DOI).
4. Check the new DOI for retractions/corrections (Scite `search_literature`
   with the DOI, no `term`, read `editorialNotices`) and record the result in
   column 26.
5. If a paper was found but didn't qualify, add it to the matching
   `excluded_*.tsv` instead, with a one-line reason — don't just drop it
   silently, the next person who finds it will re-do the work otherwise.
6. Run the four pipeline commands above. `merge_rows.py` will print a warning
   if your new DOI collides with an existing `study_id` (a real duplicate) or
   merely shares a DOI with a different `study_id` (expected when a paper has
   multiple experiments — just make sure that's actually true).
7. Add an entry to `CHANGELOG.md` (see format below) and re-send the two
   deliverables (`Conditioning_Atlas.xlsx`, `Conditioning_Atlas_dashboard.html`).

### Correcting an existing row

Never patch `merged.json`, `conditioning_atlas.tsv`, or the `.xlsx`/`.html`
outputs directly — `merge_rows.py` will blow away any such edit on the next
run, silently, because it rebuilds those files from `rows_*.tsv` every time.
**Fix the line in the source `rows_*.tsv` file**, then re-run the pipeline.
This bit the initial build once already (see `CHANGELOG.md`, 2026-08-04) — a
verification pass's corrections were applied to `merged.json` only, then lost
the next time the merge script ran. Don't repeat it.

### Periodic re-verification

This atlas was built by automated extraction against explicit inclusion
criteria, not as a registered systematic review — no PRISMA flow, no dual
independent extraction, no formal risk-of-bias assessment (see the workbook's
README sheet). Treat any given row as provisional until it's been checked
once against the primary source. A reasonable maintenance cadence:

- Before citing a specific row's numbers in a manuscript or grant, verify that
  row against the full text yourself — don't assume a prior extraction pass
  got it right.
- Periodically (e.g., quarterly, or whenever a new grant/manuscript draws on
  the atlas) spot-check a handful of high-leverage rows the way the
  2026-08-04 build did: pull full text, compare every quoted number and
  statistic, and check that a stated superlative ("longest," "first," "only
  study to...") isn't contradicted by another row in the same file.
- If you find an error, fix the `rows_*.tsv` source, note the correction in
  `CHANGELOG.md` with enough detail that someone can see *why* the old value
  was wrong (not just what the new value is), and regenerate.

### Extending the schema

If a new field is needed, add it to `SCHEMA.md` first (with its allowed
values), then to the `HDR` list in **all three** of `scripts/merge_rows.py`,
`scripts/build_xlsx.py`, and (if the dashboard should filter/display it)
`dashboard_template.html`. Every existing line in every `rows_*.tsv` needs a
value inserted at the new column position, in order — a length mismatch will
make `merge_rows.py` raise immediately (it validates field count per line), so
you'll find out fast if a file was missed.

## The Priming likelihood page

[`docs/priming-likelihood.html`](https://sr320.github.io/conditioning-atlas/priming-likelihood.html)
ranks a curated panel of marine invertebrate species by the **relative
likelihood that a sublethal priming exposure produces a favourable later-life
or offspring response**, judged from genome features (methylation machinery,
genome-wide methylation pattern, stress/immune gene family expansion, repeat
content, heterozygosity) and life-history modifiers (habitat variability,
reproductive and larval mode, generation time, photosymbiosis). Beside each
species it shows what the atlas itself contains for that species and taxon.

Be clear about what it is. No study has validated any of these features as a
predictor of priming outcome. The page is a **transparent, adjustable rubric**
whose default weights encode a reading of the environmental-epigenetics
literature; every weight, scoring rule, rationale, and source is on the page,
the sliders let a reader change them, and the "anchor check" plots the rubric
against the atlas's own *Improved* fractions so its agreement (or not) with
the evidence is visible. Output is **rank and tier** relative to the panel;
the numeric score is deliberately behind the breakdown. Assembly quality is a
badge, not part of the score, because it governs whether a response can be
characterised molecularly, not whether it occurs.

- **Adding or correcting a species**: edit `genome_features.tsv` following
  `GENOME_SCHEMA.md`. Every curated genome value needs a source in the
  `sources` column; anything a source does not state is `not reported` and the
  page imputes it from the taxon mean, flagged as such. `not reported` is never
  filled in from a congener — the *Tigriopus japonicus* row shows how to note a
  congener's value without adopting it.
- **Changing the rubric**: edit `priming_model.json`. Weights must sum to 1 and
  every scoring level must be an allowed schema value; `build_predictor.py`
  refuses to build otherwise. Record weight changes in `CHANGELOG.md` with the
  reasoning.
- **Computed values**: where no paper states a genome feature, the pipeline in
  `genomics/` computes it from the public assembly (methylation machinery by
  Pfam domain architecture, methylation pattern from CpG observed/expected
  bimodality, stress/immune family sizes by domain counts against a fixed
  baseline). Results live in `genome_derived.tsv` with method, version,
  accession, and evidence; the build fills `not reported` cells from them,
  draws them striped on the page, and prints any disagreement with a curated
  value. Curated always wins. See `genomics/README.md` for phases and status.
- **Verification status**: the initial 22-species panel (2026-09-17) was
  curated in one pass from genome and methylome papers. Treat each value as
  provisional until checked against the full text, exactly as with atlas rows.
  The pipeline already caught one: a *Tigriopus californicus* "DNMT1 absent"
  entry whose cited paper did not say so (see `CHANGELOG.md`).

## Repository maintenance

Generated deliverables are committed so visitors can download the workbook or
dashboard without installing the build tools. Regenerate them with the source
change they represent and commit them together; do not patch generated files
directly.

The `Validate and build` GitHub Actions workflow runs on pushes and pull
requests. It validates the source rows, confirms the committed JSON and TSV are
current, rebuilds the workbook and both dashboard copies, checks the GitHub
Pages output, and uploads fresh deliverables for 30 days.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the contributor workflow. Use
GitHub Issues for schema changes, verification backlogs, or larger literature
sweeps before starting work.

## License

Except where otherwise noted, this repository is licensed under the
[Creative Commons Attribution 4.0 International License](https://creativecommons.org/licenses/by/4.0/).
You may share and adapt the material for any purpose with appropriate credit, a
link to the license, and an indication of whether changes were made. See
[`LICENSE`](LICENSE) for the complete legal text.

Suggested attribution: *The Conditioning Atlas contributors, The Conditioning
Atlas, https://github.com/sr320/conditioning-atlas, CC BY 4.0.*

## Provenance and known limitations

- Sourced from PubMed, Consensus, and Scite (full-text retrieval where
  available). Elicit's systematic-review pipeline was the original intended
  tool but requires a Pro-tier API plan not available at build time — if that
  changes, Elicit's screening/extraction stages could replace or supplement
  the current PubMed/Consensus/Scite sweep.
- Every included DOI was checked via Scite for retractions, corrections, and
  expressions of concern at the time of extraction; recheck periodically,
  since a clean result then doesn't guarantee one later.
- 34 of the original 109 rows are sourced from abstracts alone (see the
  `evidence_source` column) — verify against full text before citing.
- This is a lab working resource and the scaffold for a real systematic
  review, not a substitute for one.
