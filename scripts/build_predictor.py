#!/usr/bin/env python3
"""
Build the Priming likelihood page from genome_features.tsv + priming_model.json +
merged.json + predictor_template.html.

predictor_template.html is the real source file (edit layout, charts, or styling
there). genome_features.tsv is the hand-curated species panel (see
GENOME_SCHEMA.md) and priming_model.json holds the rubric's default weights,
scoring rules, and rationale. This script:
  1. validates genome_features.tsv against the schema (header order, allowed
     values, numeric fields) and priming_model.json against itself (weights sum
     to 1, every level is an allowed schema value),
  2. matches each panel species to atlas rows in merged.json by name, including
     the synonym spellings the atlas uses (e.g. "Crassostrea gigas (Magallana
     gigas)"), and attaches the matching study_ids,
  3. injects panel, atlas, model, and footer into the __PANEL__ / __ATLAS__ /
     __MODEL__ / __FOOT__ placeholders in the template,
  4. writes the self-contained result to Priming_Likelihood.html and
     docs/priming-likelihood.html.

Never hand-edit the two outputs — they are regenerated every run.

Usage:
    python3 scripts/build_predictor.py
"""
import csv
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NR = "not reported"

HDR = [
    "species", "synonyms", "taxon", "common_name", "assembly_level", "assembly_accession",
    "genome_size_mb", "annotation", "dnmt1", "dnmt3", "tet", "methylation_pattern",
    "global_cpg_methylation_pct", "stress_immune_expansion", "hsp70_count", "iap_count",
    "expansion_notes", "te_fraction_pct", "heterozygosity_class", "reproductive_mode",
    "larval_mode", "generation_time", "symbiosis", "habitat_variability", "sources", "notes",
]

PRESENCE = {"Present", "Absent", NR}
ALLOWED = {
    "taxon": {"Bivalve", "Coral/cnidarian", "Gastropod", "Echinoderm", "Crustacean", "Polychaete/other"},
    "assembly_level": {"Chromosome", "Scaffold", "Contig", "None", NR},
    "annotation": {"Yes", "No", NR},
    "dnmt1": PRESENCE, "dnmt3": PRESENCE, "tet": PRESENCE,
    "methylation_pattern": {"Mosaic gene-body", "Global", "Low/absent", NR},
    "stress_immune_expansion": {"Expanded", "Baseline", "Contracted", NR},
    "heterozygosity_class": {"High", "Moderate", "Low", NR},
    "reproductive_mode": {"Broadcast spawner", "Brooder", "Both/variable", NR},
    "larval_mode": {"Planktotrophic", "Lecithotrophic", "Direct development", NR},
    "generation_time": {"<1 yr", "1-2 yr", "2-5 yr", ">5 yr", NR},
    "symbiosis": {"Obligate photosymbiont", "Facultative photosymbiont", "None", NR},
    "habitat_variability": {"Intertidal/estuarine", "Shallow subtidal", "Subtidal/stable", NR},
}
NUMERIC = {"genome_size_mb", "global_cpg_methylation_pct", "hsp70_count", "iap_count", "te_fraction_pct"}
FREE_TEXT = {"species", "synonyms", "common_name", "assembly_accession", "expansion_notes", "sources", "notes"}


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def load_panel(path):
    with open(path, newline="") as fh:
        reader = csv.reader(fh, delimiter="\t")
        rows = list(reader)
    if not rows:
        fail(f"{path} is empty")
    if rows[0] != HDR:
        fail(f"{path}: header does not match GENOME_SCHEMA.md.\n  expected {HDR}\n  got      {rows[0]}")
    panel, seen = [], set()
    for ln, vals in enumerate(rows[1:], start=2):
        if not any(v.strip() for v in vals):
            continue
        if len(vals) != len(HDR):
            fail(f"{path}:{ln}: expected {len(HDR)} fields, found {len(vals)}")
        r = dict(zip(HDR, (v.strip() for v in vals)))
        if not r["species"]:
            fail(f"{path}:{ln}: species is required")
        if r["species"].lower() in seen:
            fail(f"{path}:{ln}: duplicate species {r['species']}")
        seen.add(r["species"].lower())
        for k, allowed in ALLOWED.items():
            if r[k] not in allowed:
                fail(f"{path}:{ln}: {k}={r[k]!r} not in {sorted(allowed)}")
        for k in NUMERIC:
            if r[k] != NR:
                try:
                    float(r[k])
                except ValueError:
                    fail(f"{path}:{ln}: {k}={r[k]!r} must be a number or '{NR}'")
        if r["sources"] == "":
            r["sources"] = NR
        curated = [k for k in HDR[4:19] if k not in FREE_TEXT and r[k] != NR]
        if curated and r["sources"] == NR:
            fail(f"{path}:{ln}: {r['species']} has curated genome fields {curated} but no sources")
        panel.append(r)
    return panel


def load_model(path):
    with open(path) as fh:
        model = json.load(fh)
    feats = model["features"]
    total = sum(f["weight"] for f in feats)
    if abs(total - 1.0) > 1e-6:
        fail(f"{path}: feature weights sum to {total:.4f}, expected 1.0")
    ids = [f["id"] for f in feats]
    if len(set(ids)) != len(ids):
        fail(f"{path}: duplicate feature ids")
    for f in feats:
        if f["type"] == "levels":
            allowed = ALLOWED.get(f["field"])
            if allowed is None:
                fail(f"{path}: feature {f['id']} scores unknown field {f['field']}")
            bad = set(f["levels"]) - allowed
            if bad:
                fail(f"{path}: feature {f['id']} has levels {sorted(bad)} not allowed for {f['field']}")
        elif f["type"] == "bands":
            if f["field"] not in NUMERIC:
                fail(f"{path}: feature {f['id']} bands a non-numeric field {f['field']}")
            if f["bands"][-1][0] is not None:
                fail(f"{path}: feature {f['id']} bands must end with an open [null, score] band")
        elif f["type"] == "machinery":
            for k in f["fields"]:
                if ALLOWED.get(k) != PRESENCE:
                    fail(f"{path}: machinery field {k} is not a presence/absence column")
        else:
            fail(f"{path}: unknown feature type {f['type']}")
    return model


def atlas_names(species_field):
    """All binomials an atlas `species` string could be referring to, lowercased.
    Handles 'A b; C d', 'A b (C d)', 'A (C) b', and 'A cf. b'."""
    out = set()
    for part in re.split(r";\s*", species_field):
        p = part.strip()
        if not p:
            continue
        m = re.match(r"^(\w+)\s*\((\w+)\)\s+(\w+)", p)          # Magallana (Crassostrea) gigas
        if m:
            out.add(f"{m.group(1)} {m.group(3)}".lower())
            out.add(f"{m.group(2)} {m.group(3)}".lower())
            continue
        m = re.match(r"^([\w.]+\s+[\w.]+)\s*\(([\w.]+\s+[\w.]+)\)", p)  # Crassostrea gigas (Magallana gigas)
        if m:
            out.add(m.group(1).lower())
            out.add(m.group(2).lower())
            continue
        out.add(re.sub(r"\bcf\.\s*", "", p).lower())
    return out


def match_atlas(panel, atlas):
    # Attach row *indices* rather than study_ids: the atlas has a few study_ids
    # shared by two different papers, so the id alone is not a safe key.
    for r in panel:
        names = {r["species"].lower()} | {s.strip().lower() for s in r["synonyms"].split(";") if s.strip()}
        r["atlas_idx"] = [i for i, a in enumerate(atlas) if names & atlas_names(a["species"])]
    matched = {i for r in panel for i in r["atlas_idx"]}
    unmatched = sorted({a["species"] for i, a in enumerate(atlas) if i not in matched})
    return unmatched


DERIVED_FIELDS = set(ALLOWED) | NUMERIC   # panel columns a computed value may fill


def merge_derived(panel, path):
    """Fill `not reported` panel cells from genome_derived.tsv (values computed from
    the assemblies by genomics/). Curated values always win; a computed value that
    disagrees with a curated one is reported, not applied. Each filled cell is
    recorded in row["computed"][field] with its provenance so the page can show it
    as a distinct basis. BUSCO completeness is carried separately for the badge."""
    for r in panel:
        r["computed"], r["busco"] = {}, None
    if not os.path.exists(path):
        return 0, []
    with open(path, newline="") as fh:
        derived = list(csv.DictReader(fh, delimiter="\t"))
    by_species = {}
    for d in derived:
        by_species.setdefault(d["species"], []).append(d)
    filled, conflicts = 0, []
    for r in panel:
        for d in by_species.get(r["species"], []):
            f, v = d["feature"], d["value"].strip()
            if f == "busco_complete_pct":
                try:
                    r["busco"] = max(r["busco"] or 0.0, float(v))
                except ValueError:
                    pass
                continue
            if f not in DERIVED_FIELDS or v == NR:
                continue
            if f in ALLOWED and v not in ALLOWED[f]:
                fail(f"genome_derived.tsv: {r['species']} {f}={v!r} is not an allowed value")
            if f in NUMERIC:
                try:
                    float(v)
                except ValueError:
                    fail(f"genome_derived.tsv: {r['species']} {f}={v!r} is not numeric")
            if r[f] == NR:
                if f in r["computed"]:
                    continue  # first method listed wins; later methods for the same cell are ignored
                r[f] = v
                r["computed"][f] = {k: d.get(k, "") for k in ("value", "method", "tool_version", "database", "accession", "date", "evidence")}
                filled += 1
            elif r[f] != v:
                conflicts.append((r["species"], f, r[f], v, d.get("method", "")))
    return filled, conflicts


def main():
    panel = load_panel(os.path.join(ROOT, "genome_features.tsv"))
    model = load_model(os.path.join(ROOT, "priming_model.json"))
    with open(os.path.join(ROOT, "merged.json")) as fh:
        atlas = json.load(fh)

    filled, conflicts = merge_derived(panel, os.path.join(ROOT, "genome_derived.tsv"))
    print(f"Computed values: {filled} cells filled from genome_derived.tsv"
          + (f"; {len(conflicts)} curated/computed disagreements (curated kept):" if conflicts else ""))
    for sp, f, cur, comp, method in conflicts:
        print(f"  {sp}: {f} curated={cur!r} computed={comp!r} [{method}]")

    unmatched = match_atlas(panel, atlas)
    with_rows = sum(1 for r in panel if r["atlas_idx"])
    n_matched = len({i for r in panel for i in r["atlas_idx"]})
    print(f"Panel: {len(panel)} species, {with_rows} with atlas rows; "
          f"{len(atlas) - n_matched} atlas rows unmatched across {len(unmatched)} species strings")

    atlas_slim = [
        {k: a[k] for k in ("study_id", "doi", "year", "species", "taxon", "stressor", "stressor_category",
                           "conditioning_stage", "generations", "challenge", "persistence_days", "decay",
                           "direction", "effect_magnitude", "molecular_layers", "applied_framing",
                           "evidence_source")}
        for a in atlas
    ]

    foot = (
        "The species panel is hand-curated from genome and methylome papers listed per species; every value is "
        "traceable to a source in the row's `sources` field. Cells no source states are filled, where possible, with "
        "values computed from the public assembly by the repository's genomics pipeline (striped in the breakdown; "
        f"{filled} cells at this build) and otherwise imputed at taxon level (hatched). Life-history categories rest on standard natural "
        "history. The rubric weights encode a reading of the environmental-epigenetics literature, not a fitted "
        "model, and rank and tier are relative to this panel only. The atlas evidence shown beside each species "
        "comes from the Conditioning Atlas's own rows and inherits their caveats. "
        f"Rubric v{model['version']} · {len(panel)} species in panel · {with_rows} with atlas evidence · "
        f"{len(atlas)} atlas experiments · built {datetime.date.today().isoformat()}."
    )

    tpl_path = os.path.join(ROOT, "predictor_template.html")
    with open(tpl_path) as fh:
        tpl = fh.read()
    for ph in ("__PANEL__", "__ATLAS__", "__MODEL__", "__FOOT__"):
        if ph not in tpl:
            fail(f"{tpl_path} is missing the {ph} placeholder")

    html = (tpl.replace("__PANEL__", json.dumps(panel, separators=(",", ":")))
               .replace("__ATLAS__", json.dumps(atlas_slim, separators=(",", ":")))
               .replace("__MODEL__", json.dumps(model, separators=(",", ":")))
               .replace("__FOOT__", json.dumps(foot)))

    out_paths = [
        os.path.join(ROOT, "Priming_Likelihood.html"),
        os.path.join(ROOT, "docs", "priming-likelihood.html"),
    ]
    os.makedirs(os.path.dirname(out_paths[1]), exist_ok=True)
    for out_path in out_paths:
        with open(out_path, "w") as fh:
            fh.write(html)
        print(f"Wrote {out_path} ({len(html) / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
