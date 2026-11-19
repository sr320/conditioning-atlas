# Weekly sweep: discovery and screening

This directory holds phase 1 of [`WEEKLY_SWEEP_PLAN.md`](../WEEKLY_SWEEP_PLAN.md):

1. Find candidate papers.
2. Drop the ones the atlas already knows.
3. Screen the rest against the inclusion criteria in `SCHEMA.md`.
4. Record the decisions in the atlas's own files and open a pull request.

Extraction is still done by a person, so nothing here writes to `rows_*.tsv`.

## The weekly workflow

`.github/workflows/weekly-sweep.yml` runs every Monday at 14:00 UTC. It can
also be started by hand from the Actions tab, with an optional date window.

**What it does:**

1. Searches the last 14 days, which overlap the previous run.
2. Screens the new papers with the Message Batches API. A cap of 400 papers
   bounds the cost.
3. Runs `sweep/write.py`, which routes each decision:

   | Decision | Goes to |
   |---|---|
   | `exclude` | `excluded_<cluster>.tsv` |
   | `include` | `pending_review.tsv`, as "Screened include, needs extraction" |
   | `needs_full_text` | `pending_review.tsv`, as "Needs full text or scope call" |
   | `preprint_hold` | `pending_review.tsv`, as "Preprint" |

   Every screened paper is also added to `sweep_state/seen.tsv`, so it is
   never screened twice.
4. Drafts a `CHANGELOG.md` entry and rebuilds every deliverable, with
   LibreOffice recalculating the workbook.
5. Opens a pull request on `sweep/<ISO week>`. The PR body lists every kept
   paper with the model's reason, and the exclusions in a collapsed list.

A week with no new papers opens no PR. Nothing is ever merged automatically.

**Reviewing a sweep PR.** Moving a paper you disagree with between files is
enough. For example, cut its line from `excluded_*.tsv` and add it to
`pending_review.tsv`. The next sweep will not screen it again, because it
stays in `seen.tsv`.

**Setup, once.**

- **Secret `ANTHROPIC_API_KEY`** (required).
- **Secret `OPENALEX_API_KEY`** (recommended). Without it, OpenAlex can run
  out of budget partway through a week.
- **Variable `CONTACT_EMAIL`.**
- **Pull-request permission.** Under Settings → Actions → General → Workflow
  permissions, tick "Allow GitHub Actions to create and approve pull
  requests".
- **Checks on sweep PRs.** A PR opened with the built-in token does not
  trigger `validate.yml`, so the sweep job runs the same build and checks
  itself before opening the PR.

## Setup

The scripts need Python 3.10 or later. The Anthropic SDK does not support the
system Python 3.8.

```bash
uv venv -p 3.13 .venv
uv pip install --python .venv/bin/python -r requirements.txt -r sweep/requirements.txt
```

**Credentials.** The scripts read the Claude API credentials from
`ANTHROPIC_API_KEY`, or from an `ant auth login` profile.

**Optional environment variables:**

- `CONTACT_EMAIL` joins the polite pools for OpenAlex and NCBI. The NCBI ID
  converter rejects a placeholder address.
- `OPENALEX_API_KEY`: without one, OpenAlex shares a $0.10/day budget across
  every user on your IP address. The backtest ran out of it partway through.

## Running

```bash
.venv/bin/python -m sweep.discover --since 2026-11-01 --until 2026-11-19 --run-id 2026-W47
.venv/bin/python -m sweep.screen   --run-id 2026-W47            # Message Batches, 50% cheaper
.venv/bin/python -m sweep.screen   --run-id 2026-W47 --direct   # concurrent calls, for quick iteration
.venv/bin/python -m sweep.write    --run-id 2026-W47            # edits excluded_*, pending_review, seen, CHANGELOG
```

Each run writes its files to `sweep_runs/<run_id>/`:

- **`raw_<source>.jsonl` and `hits.jsonl`:** raw and merged search results.
  These are not tracked in git. Pass `--reuse openalex` to rebuild a run from
  the cached results without querying again.
- **`candidates.jsonl`:** papers that are new to the atlas and passed the term
  prefilter.
- **`decisions.jsonl`:** one structured decision per candidate. The decision is
  `include`, `exclude`, `needs_full_text` or `preprint_hold`, with a verdict on
  each criterion, a cluster and a one-line reason.
- **`screen_system_prompt.md`:** the exact prompt the model saw.

Re-running `screen` only pays for papers it has not already decided.

**What the sweep searches for.** The search terms are in `queries.yaml`, and
the screening instructions are in `prompts/screen_system.md`. The prompt is
filled with precedents from the atlas itself: one line per included
experiment, plus every recorded exclusion reason.

## Backtest against the October 2026 manual sweep

```bash
.venv/bin/python -m sweep.discover --since 2026-03-01 --until 2026-10-25 \
    --run-id backtest-2026-10 --known-ref 'fc079b3^'
.venv/bin/python -m sweep.screen   --run-id backtest-2026-10 --direct --precedent-ref 'fc079b3^'
.venv/bin/python -m sweep.backtest --run-id backtest-2026-10
```

**How the backtest is set up.**

- **Answers kept out of the prompt.** `--known-ref` and `--precedent-ref` make
  both the dedupe step and the screening precedents use the atlas as it was
  *before* commit `fc079b3`. That commit's own decisions are never in the
  prompt.
- **Ground truth.** The answer key is what `fc079b3` added: 27 included
  papers, 64 exclusions and 26 holds (7 preprints and 19 undecided).
- **Full report.** The model's reasons are in
  [`sweep_runs/backtest-2026-10/backtest.md`](../sweep_runs/backtest-2026-10/backtest.md).

**Results (2026-11-19, `claude-opus-5-5`, effort `low`)**

| | included papers (27) |
|---|---|
| Found by discovery | 24 (89%) |
| Screened `include` | 21 |
| Screened `needs_full_text` (still reaches a person) | 2 |
| Screened `exclude` | 1 |
| **End-to-end recall** | **23/27 (85%)**; the target was ≥95% |

**Where the four misses came from:**

- **Agius_2026 and Yang_2026** were registered in January and February.
  That is before any date window, so a weekly sweep would only catch them in
  the week they appeared.
- **Boodraj_2026** (Frontiers) is not in Europe PMC or PubMed. OpenAlex
  probably has it, but the free OpenAlex budget ran out after 200 of 581
  hits.
- **BaptistaNobre_2026** was excluded by the model, which read "parental reef
  thermal history" as a provenance correlation, not conditioning. The
  manual sweep counted it as a natural-history conditioning contrast. The
  prompt was not tuned to fix this, because tuning on the test set would
  overstate recall.

**Other findings:**

- **Agreement on the exclusions both sweeps saw:** 16 of 17. The 17th went to
  `needs_full_text`: a predator-cue paper the model flagged as a scope call.
- **Papers the manual sweep never saw:** discovery returned 404. The model
  marked 11 `include`, 8 `preprint_hold` and 16 `needs_full_text`, and
  excluded 369. Several look like real misses on a first read: the Tigriopus
  florfenicol paper (intergenerational), three *Mytilus californianus* papers
  pairing heat acclimation with a heat-shock challenge, lobster parental
  emamectin exposure, and *Penaeus* zinc pre-exposure before a WSSV challenge.
  None has been checked against the full text.
- **Cost:** about $6.60 to screen 608 records with direct calls. Batch mode
  would halve that. The 24.5k-token cached system prompt made up most of the
  input cost, about 1.1¢ per paper. This window was 34 weeks long, so a
  weekly run should screen roughly 15–30 papers for well under $1.

**Bugs the backtest caught, now fixed:**

- The PubMed parser took DOIs from each paper's *reference list*, which
  created 138 phantom records with the wrong DOI.
- Europe PMC returns some PMC records without a DOI, so they never matched
  the dedupe step. They are now recovered through the NCBI ID converter.
- OpenAlex's `search=` parameter matches full text (15k hits). It was
  switched to `title_and_abstract.search` (581 hits).
