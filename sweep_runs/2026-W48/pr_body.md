Automated weekly literature sweep **2026-W48** (2026-11-10 to 2026-11-24).

15 papers were new to the atlas and were screened from title and abstract by `claude-opus-5-5`: **13** exclude, **1** include, **1** needs_full_text.

This is phase 1 of `WEEKLY_SWEEP_PLAN.md`, so no atlas rows are added. Screened includes and holds go to `pending_review.tsv`, exclusions go to `excluded_*.tsv`, and every screened DOI goes to `sweep_state/seen.tsv`.

**To review:**

- Check the papers below that the model kept.
- Skim the exclusions.
- Fix any decision you disagree with by moving the line between files in this PR.
- Merge.

## Kept for a person to look at

| decision | paper | species | why |
|---|---|---|---|
| `include` | [Food ration affects mRNA processing, translation, proteostasis and cytoskeletal responses during heat shock in](https://doi.org/10.1242/jeb.252969) | Mytilus californianus | Bivalve acclimated to high vs low aerial low-tide temperature (crossed with food ration), then given a later acute 33 C aerial heat shock with 1 h and 25 h recovery; prior thermal conditioning followed by a later challenge satisfies criteria 2 and 3, like the Georgoulis_2021 and Galati_2026 rows |
| `needs_full_text` | [A multi-epitope vaccine based on AdeK, PirA, and Omp22 elicits specific antibodies binding to Carbapenem-resis](https://doi.org/10.1016/j.intimp.2026.117689) |  | model declined to screen (refusal, category bio); screen by hand |

<details><summary>Excluded (13)</summary>

- [Conserved Transcriptomic Heat Stress Response Signatures in Coral Recruits From Crosses of Thermally Distinct ](https://doi.org/10.1111/mec.70622) — Selective breeding / crosses of broodstock from thermally distinct reefs, not a sublethal priming exposure; recruits given a single heat stress with no conditioning phase (fails criterion 2), consistent with prior exclusions of warm x cool cross designs
- [Comparative ecotoxicity of aluminium-based galvanic anodes and impressed current on the Pacific oyster (Crasso](https://doi.org/10.1016/j.jhazmat.2026.143933) — Single-exposure embryo-larval dose-response toxicity test with effects scored at the end of exposure; no priming phase followed by a later or offspring assessment (fails criteria 2 and 3)
- [Parity-selective tuning of higher-order mode nonlinearities in a doubly clamped MEMS beam resonator](https://doi.org/10.21203/rs.3.rs-11550498/v1) — Physics/engineering study of nonlinearities in a GaAs MEMS beam resonator, not a marine invertebrate (fails inclusion criterion 1); no priming exposure or later assessment; preprint hold not applicable since it would be excluded anyway
- [Characterizing the molecular determinants of sliding clamp binding in Bacillus subtilis.](https://doi.org/10.1002/pro.70880) — In vitro biochemical study of bacterial sliding clamp binding (Bacillus subtilis, E. coli) - not a marine invertebrate, fails inclusion criterion 1; no priming exposure or later assessment
- [Diverging light-responsive behaviors in genetically similar strains of Hydra vulgaris](https://doi.org/10.64898/2026.11.18.767650) — Freshwater cnidarian (Hydra vulgaris) strain comparison of phototactic behaviour - fails the marine/estuarine criterion 1, with no priming exposure or later assessment (criteria 2-3); preprint hold not applicable since it would be excluded anyway
- [Universal Versus Selective Sampling of Umbilical Cord Gases in University-Based, Academic Community-Based, and](https://doi.org/10.7759/cureus.118240) — Human clinical survey of obstetric providers on umbilical cord gas sampling practices - not a marine invertebrate (fails inclusion criterion 1); no priming exposure or later assessment
- [Discriminative value of serum adiponectin as a potential adjunctive marker for HOMA-IR-defined insulin resista](https://doi.org/10.1186/s12902-026-02512-7) — Human clinical biomarker study (adiponectin and insulin resistance in women with recurrent spontaneous abortion) - not a marine invertebrate, fails inclusion criterion 1; no priming exposure or later assessment
- [A Postbiotic Mixture of Two Heat-Inactivated Lactobacilli Preserves Gut Microbiome Integrity in Pacific White ](https://doi.org/10.3390/fermentation12110541) — Continuous 30-day dietary postbiotic feed additive with gut microbiome profiled at the end of feeding; a feed additive is not a priming exposure and no later challenge or later-life outcome was measured (fails criteria 2 and 3)
- [Starfish-FL: Harnessing Agentic Federated Analytics](https://doi.org/10.1145/3843774) — Computing/software paper on federated learning for healthcare analytics ('Starfish' is a software name, not an echinoderm) - not a marine invertebrate (fails inclusion criterion 1); no priming exposure or later assessment
- [Functional interplay between retinoid X receptor and juvenile hormone analog regulates offspring production in](https://doi.org/10.1242/jeb.251768) — Crustacean endocrine/gene-function study (RXR RNAi knockdown and JH III injection) with reproductive outcomes measured as the direct response; no sublethal priming exposure followed by a later challenge or offspring stress assessment (fails criterion 2)
- [From Bycatch to Blood Health: A Participatory Action Research on Family Empowerment through Baby Crab (Portunu](https://doi.org/10.69124/mh.2026.19659) — Human nutrition study of pregnant women; the crab is only a food ingredient, not the experimental animal, so it fails inclusion criterion 1. There is also no priming exposure or later assessment of a marine invertebrate.
- [Beyond Alignment: Whitening Geometry, Profile Synthesis, and Heterogeneous Ensembles for Cross-Environment WiF](https://doi.org/10.48550/arxiv.2611.25831) — Machine-learning paper on cross-environment WiFi action recognition (CORAL is a domain-alignment method, not coral) - not a marine invertebrate, fails inclusion criterion 1; preprint hold not applicable since it would be excluded anyway
- [Leveraging Local English Communication Skills as a Catalyst for Sustainable Tourism Growth: A Case Study of Se](https://doi.org/10.66914/0fsqeb52) — Human qualitative study of English communication skills in coastal tourism (corals mentioned only in signage) - not a marine invertebrate, fails inclusion criterion 1; no priming exposure or later assessment

</details>

<sub>Tokens: 12,357 input, 504,938 cached, 2,454 output. Run files: `sweep_runs/2026-W48/`.</sub>

🤖 Generated with [Claude Code](https://claude.com/claude-code)
