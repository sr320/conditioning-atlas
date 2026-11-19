# Plan: weekly automated literature sweep

Goal: every week, find newly published or indexed conditioning and priming
papers, screen them against `SCHEMA.md`, and extract the qualifying ones. The
results arrive as a **pull request** that a person reviews and merges. Merging
rebuilds the dashboard, workbook and Pages site with the existing pipeline.
Nothing reaches `main` without review. The atlas has always required that rows
be checked against the source, and automation does not change that.

## Design at a glance

```
GitHub Actions cron (Mon 06:00 PT) ─┐
                                    ▼
 1. discover   OpenAlex · PubMed · Crossref · Europe PMC · bioRxiv   (free APIs, no LLM)
                                    ▼
 2. dedupe     against rows_*.tsv, excluded_*.tsv, pending_review.tsv, sweep_state/seen.tsv
                                    ▼
 3. screen     Claude API (Message Batches, structured output) → include / exclude / needs full text
                                    ▼
 4. full text  Europe PMC / PMC OA XML, Unpaywall OA PDF → else "Abstract only"
                                    ▼
 5. extract    Claude API, 27-field structured output + verbatim evidence quotes
                                    ▼
 6. validate   field count, enums, no tabs, DOI resolves, editorial notices
                                    ▼
 7. write      append rows / excluded / pending → run the 5-step pipeline → CHANGELOG draft
                                    ▼
 8. open PR    branch sweep/2026-Www, per-paper review table in the PR body
```

A week with no new candidates opens no PR. It only advances the state file.

## 1. Discovery (deterministic, no LLM)

- **Queries live in data.** `sweep/queries.yaml` holds one block per cluster
  (bivalve temp/pH, coral, immune, other), each with the search strings for
  each source. Query changes can be reviewed in a PR, as `priming_model.json` is.
- **Sources and date fields.** The CHANGELOG notes that PubMed date filters
  were unreliable, so each source uses its *indexing* date and the window
  overlaps the previous one:
  - OpenAlex `/works?filter=from_created_date:…,to_created_date:…&search=…`
    (polite pool `mailto`). This is the broadest net and covers most journals.
  - PubMed E-utilities `esearch` on `[crdt]` (create date), plus `efetch` for
    abstracts. Use `NCBI_API_KEY` for the rate limit.
  - Crossref `/works?filter=from-index-date:…` to catch journals that are slow
    to reach the other sources.
  - Europe PMC REST: it indexes preprints, and its `fullTextXML` serves step 4.
  - bioRxiv `/details/biorxiv/{from}/{to}`, filtered to ecology, zoology,
    genomics and molecular biology, then a keyword prefilter.
- **Window.** The last 14 days, re-run weekly. The overlap is harmless because
  the dedupe step removes repeats.
- **Normalize** to one record per DOI: title, abstract, authors, journal,
  date, OA status, PMID/PMCID, and preprint flag.

## 2. Dedupe

Lower-case DOIs and match them against every DOI already in `rows_*.tsv`,
`excluded_*.tsv`, `pending_review.tsv`, and a new
`sweep_state/seen.tsv` (DOI, first_seen, decision, run_id). A screened DOI is
never screened again. A preprint already in `pending_review.tsv` is checked in
step 8b instead.

## 3. Screening (Claude API)

- **Model.** `claude-opus-5-5` at `effort: low`, through the **Message Batches API**.
  Batches cost 50% less, and a weekly job does not need low latency.
- **Prompt.** The system prompt holds `SCHEMA.md`'s inclusion criteria plus
  about 20 worked precedents taken from the `excluded_*.tsv` reasons and the
  judgement calls in the CHANGELOG (the Ananda_2026 vaccine arm, companion
  papers folded into one row, preprint duplicates). It is cached with
  `cache_control`, so each abstract costs only its own tokens.
- **Structured output** (`output_config.format`, JSON schema):
  `{doi, criteria: {marine_invert, priming_exposure, later_outcome, primary_empirical},
  decision: include | exclude | needs_full_text | preprint_hold,
  cluster: bivalve_temp_ph | coral | immune | other, reason (one line)}`.
- **Routing.**
  - `exclude` → `excluded_<cluster>.tsv` with the reason.
  - `include` → step 4.
  - `needs_full_text`, and preprints that otherwise qualify → `pending_review.tsv`,
    which matches the current convention.

## 4. Full-text retrieval

In order: Europe PMC `fullTextXML` (when there is a PMCID), the PMC OA
service, then the Unpaywall `best_oa_location` PDF, which goes to the API as a
`document` block. Retrieval uses only legitimate OA routes, with no
scraping. The October sweep found that Elsevier, Springer and MDPI pages
refused automated access. When retrieval fails, the paper falls back to
`Abstract only`, and the PR flags it for a manual full-text pass.

## 5. Extraction (Claude API)

- **Model.** `claude-opus-5-5` at `effort: high`, with adaptive thinking and
  streaming. Extraction runs on only a handful of papers a week, and it
  produces the fields the atlas exists for.
- **Prompt.** The system prompt is all of `SCHEMA.md`, plus about three gold
  example rows (full-text rows from the October sweep) and the conventions
  from the CHANGELOG. It is cached.
- **Structured output.** An array of experiments, each holding the 27 fields
  as typed properties with the allowed values encoded as `enum`s. Free-text
  fields stay strings. **The model also returns a verbatim `evidence` quote
  for each priority field** (`dose_treatment`, `duration`, `persistence_days`,
  `decay`, `concordance`, `effect_magnitude`), or `null` when it set the field
  to `not reported`. The quotes go to `sweep_runs/<run_id>/evidence.jsonl` and
  into the PR body, so a reviewer can check each number without opening the
  paper.
- **Never-infer guard.** A numeric field whose quote does not contain that
  number is reset to `not reported`, and the reset is noted in `notes`. The
  check is in code, not in the prompt.
- **Splits.** The model decides on `a`/`b` splits per experiment, following the
  schema rule. `study_id` collisions are resolved in code against the existing
  IDs.

## 6. Validation (code, before anything is written)

- Each row has exactly 27 fields, no literal tabs, and enum fields within the
  allowed set. This needs a decision on the open `conditioning_stage = not reported`
  question in the CHANGELOG, which the validator must either allow or reject.
- The DOI resolves in Crossref, and the PMID matches the DOI through the NCBI
  ID converter.
- **Editorial notice (field 26).** Read Crossref `update-to` and `relation`
  (which includes the Retraction Watch data). If a scite API key is available,
  query scite as well. Otherwise the field says `Not checked`, and the PR lists
  those DOIs for the manual scite step that the README describes.

## 7. Write and build

1. Append rows to `rows_<cluster>.tsv` and exclusions to `excluded_<cluster>.tsv`.
   Add held items to `pending_review.tsv` and write the seen DOIs to
   `sweep_state/seen.tsv`.
2. Run the existing pipeline unchanged (`merge_rows.py` → `build_xlsx.py` →
   `recalc_xlsx.py` → `build_dashboard.py` → `build_predictor.py`). The
   workflow installs `libreoffice-calc`, which fixes the missing cached
   formula values reported in the last two CHANGELOG entries.
3. Prepend a drafted `CHANGELOG.md` entry with the counts (screened, included,
   excluded, held), the rows added per file, the abstract-only rows, and the
   judgement calls the model flagged.
4. Add a "Literature current through YYYY-MM-DD" line to the dashboard footer.
   `build_dashboard.py` reads it from `sweep_state/last_run.json`.

## 8. Pull request, plus two weekly maintenance checks

- **a. The PR.** It goes on branch `sweep/<ISO-week>` and contains a table with
  one line per new row: study_id, the DOI link, the `evidence_source`, the
  priority fields with their evidence quotes, and ⚠ marks on fields that were
  reset or need judgement. The existing `Validate and build` workflow runs on
  it. The PR is never auto-merged.
- **b. Preprint promotion.** For each preprint in `pending_review.tsv`, check
  Crossref `is-preprint-of` and the bioRxiv `/pubs` endpoint. If a
  peer-reviewed version exists, run it through steps 4–7 and remove it from
  pending.
- **c. Retraction recheck.** The README says to recheck periodically. Each week,
  re-query editorial notices for a rotating eighth of the existing DOIs, so
  every row is rechecked about every two months. A change goes in the PR as a
  proposed field-26 edit.

## Files to add

| Path | Purpose |
|---|---|
| `.github/workflows/weekly-sweep.yml` | `schedule` (cron) + `workflow_dispatch` with a `since` input for backfills. Permissions: `contents: write`, `pull-requests: write` |
| `sweep/queries.yaml` | Per-cluster, per-source query strings |
| `sweep/discover.py` | Steps 1–2 |
| `sweep/screen.py` | Step 3 (batch submit, poll, collect) |
| `sweep/fulltext.py` | Step 4 |
| `sweep/extract.py` | Step 5, including the evidence-quote guard |
| `sweep/validate_rows.py` | Step 6. It also runs in `validate.yml`, so hand-added rows get the same checks |
| `sweep/prompts/` | Screening and extraction system prompts and gold examples, as plain text so changes show in diffs |
| `sweep/run.py` | Orchestrates the steps and writes `sweep_runs/<run_id>/` (raw hits, decisions, evidence, token usage) |
| `sweep_state/seen.tsv`, `sweep_state/last_run.json` | Persistent state, committed with each PR |

New dependencies: `anthropic`, `httpx`, `pyyaml`.
Repository secrets: `ANTHROPIC_API_KEY`, `NCBI_API_KEY` (optional),
`CONTACT_EMAIL` (for the OpenAlex and Unpaywall polite pools), and
`SCITE_API_KEY` (optional).

## Cost (to be checked on the first runs)

Assume about 100–250 new abstracts a week after dedupe and about 3–8
extractions. Screening on the Batches API with a cached system prompt costs
well under $1–2. Extraction at high effort, with 20–40k tokens of full text
per paper, costs roughly $1–4. The expected total is **a few dollars a week**.
Each run logs `usage` to `sweep_runs/<run_id>/usage.json`, so the real figure
is visible from the first PR. A hard cap in `run.py` stops a run and opens the
PR as-is if a week's spend passes a set limit.

## Rollout

0. **Backtest (do first).** Run discovery and screening over 2026-06-01 →
   2026-10-25 and compare the result with the October manual sweep: 27
   included, 64 excluded and 19 held out of 117. The target is recall of the
   included papers ≥ 0.95. Then run extraction on the 10 full-text papers and
   compare the priority fields with the merged rows. Tune the prompts and
   queries before anything runs on a schedule.
1. **Discovery + screening only.** The PRs add only `pending_review.tsv` and
   `excluded_*.tsv` entries, and a person extracts. This builds trust in the
   screen at low risk.
2. **Add extraction.** The PRs carry the new rows with their evidence quotes.
3. **Add preprint promotion and the rotating retraction recheck.**

## Decisions needed

- **Model per stage.** The plan uses Opus 5.5 for both stages, at low effort
  for screening. Haiku 5.5 or Sonnet 5.5 would cut the screening cost further.
  The backtest can show whether recall holds.
- **The `conditioning_stage = not reported` convention**, still open since the
  October sweep. The validator needs an answer.
- **Who reviews** the weekly PR. It could be assigned automatically through
  CODEOWNERS.
- **Scite access.** Without an API key, field 26 stays `Not checked` until
  someone runs the manual scite step.
- **Where it runs.** This plan uses GitHub Actions and the Claude API. A Claude
  Code cloud routine (`/schedule`) using the PubMed, Consensus and scite
  connectors would be a lower-code alternative. It is harder to audit and
  reproduce, and its query behaviour is less deterministic, so it is not the
  recommendation here.
