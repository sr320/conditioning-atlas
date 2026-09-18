# Priming likelihood — genome and life-history panel schema

This file is the contract for `genome_features.tsv`, the hand-edited source
behind the **Priming likelihood** page (`docs/priming-likelihood.html`). One
row per **species**. The panel may include species that are not in the
atlas (useful comparators such as *Tigriopus californicus*), and it does not
have to cover every atlas species.

The page ranks the panel by a transparent, weighted rubric defined in
`priming_model.json`. It is a hypothesis-generating rubric, not a validated
model: no study has yet shown that these genome features predict priming
outcomes in marine invertebrates. Every default weight and every scoring rule
is exposed on the page and adjustable by the reader.

Output format: **tab-separated with a header row** (unlike `rows_*.tsv`, which
has no header — the header lets `scripts/build_predictor.py` check column order
by name). Never use a literal tab inside a field. Use `; ` to separate items
within a field. Use `not reported` when no source states the value. **Never
infer a value from a congener or from taxon-level generalisations** — enter
`not reported`, and if a congener's value is informative say so in `notes`
(the *Tigriopus japonicus* row is the worked example). The build step imputes
missing features from the taxon mean and flags them as imputed on the page;
that is the page's job, not the curator's.

| # | field | allowed values / format | scored? |
|---|-------|------------------------|---------|
| 1 | species | full Latin binomial, matching the spelling used in `rows_*.tsv` where the species is in the atlas | key |
| 2 | synonyms | other names the atlas uses for the same species (e.g. `Magallana gigas`), `; `-separated, or empty | key |
| 3 | taxon | `Bivalve` \| `Coral/cnidarian` \| `Gastropod` \| `Echinoderm` \| `Crustacean` \| `Polychaete/other` — same vocabulary as `SCHEMA.md` | grouping |
| 4 | common_name | free text | display |
| 5 | assembly_level | `Chromosome` \| `Scaffold` \| `Contig` \| `None` \| `not reported` | tractability badge only |
| 6 | assembly_accession | NCBI `GCA_`/`GCF_` accession, or `not reported` | display |
| 7 | genome_size_mb | assembly size in megabases (number), or `not reported` | display |
| 8 | annotation | `Yes` \| `No` \| `not reported` — is a protein-coding gene annotation publicly available? | tractability badge only |
| 9 | dnmt1 | `Present` \| `Absent` \| `not reported` — maintenance methyltransferase | machinery |
| 10 | dnmt3 | `Present` \| `Absent` \| `not reported` — de novo methyltransferase | machinery |
| 11 | tet | `Present` \| `Absent` \| `not reported` — TET demethylase | machinery |
| 12 | methylation_pattern | `Mosaic gene-body` \| `Global` \| `Low/absent` \| `not reported` — the genome-wide CpG methylation landscape as characterised by WGBS, RRBS, MBD-seq, or CpG O/E analysis | pattern |
| 13 | global_cpg_methylation_pct | percent of CpGs methylated genome-wide (number), or `not reported`; display only, the categorical pattern is what is scored | display |
| 14 | stress_immune_expansion | `Expanded` \| `Baseline` \| `Contracted` \| `not reported` — did the genome paper report lineage-specific expansion of stress-response or innate-immune gene families (HSP70, IAP, antioxidant, pattern-recognition receptors, etc.)? | expansion |
| 15 | hsp70_count | number of HSP70-family genes reported, or `not reported` | display |
| 16 | iap_count | number of inhibitor-of-apoptosis genes reported, or `not reported` | display |
| 17 | expansion_notes | which families, per the source; free text | display |
| 18 | te_fraction_pct | percent of the assembly annotated as repeats/transposable elements (number), or `not reported` | plasticity substrate |
| 19 | heterozygosity_class | `High` \| `Moderate` \| `Low` \| `not reported` — as characterised by the genome paper (SNP density, pan-genome PAV, or reported heterozygosity) | plasticity substrate |
| 20 | reproductive_mode | `Broadcast spawner` \| `Brooder` \| `Both/variable` \| `not reported` | life history |
| 21 | larval_mode | `Planktotrophic` \| `Lecithotrophic` \| `Direct development` \| `not reported` | life history |
| 22 | generation_time | `<1 yr` \| `1-2 yr` \| `2-5 yr` \| `>5 yr` \| `not reported` — typical age at first reproduction | life history |
| 23 | symbiosis | `Obligate photosymbiont` \| `Facultative photosymbiont` \| `None` \| `not reported` — algal photosymbiosis specifically; bacterial symbionts go in notes | life history |
| 24 | habitat_variability | `Intertidal/estuarine` \| `Shallow subtidal` \| `Subtidal/stable` \| `not reported` — the environmental variability the species' adult habitat exposes it to | life history |
| 25 | sources | `; `-separated bare DOIs (no `https://`), or `Author Year Journal` / an NCBI accession when no DOI exists; every non-`not reported` value in the genome columns (5–19) must be traceable to one of these, and the build refuses a row that has curated genome values but no source. Life-history columns (20–24) may rest on standard natural history; flag anything contested in `notes` | provenance |
| 26 | notes | caveats, congener information, anything a lab would want flagged | display |

## How the rubric uses these fields

Scored features are grouped as **genome** (machinery, pattern, expansion,
plasticity substrate) and **life history**. Each categorical value maps to a
0–1 score via the `levels` table in `priming_model.json`; numeric features use
the `bands` table there. The final score is a weighted sum with weights
normalised to 1. The page shows **rank and tier** (top, middle, bottom third
of the panel); the numeric score is available in the breakdown.

Missing (`not reported`) features are imputed as the mean score of the other
panel members in the same taxon, or 0.5 if fewer than two are known, and the
species' **coverage** (the weight fraction resting on curated rather than
imputed values) is displayed alongside its rank.

`assembly_level` and `annotation` are deliberately **not** scored. They affect
whether a priming response can be demonstrated molecularly, not whether it is
likely to occur, so they appear as a tractability badge.

## Adding or correcting a species

1. Pull the genome paper and, where available, a methylome paper. Abstracts
   rarely state repeat content, gene family counts, or methylation machinery.
2. Fill every field you can source; leave the rest `not reported`.
3. Put the DOI of every paper you used in `sources`.
4. Run `python3 scripts/build_predictor.py`. It validates the header, allowed
   values, and numeric fields, and will refuse to build on a bad row.
5. Record the addition in `CHANGELOG.md`.
