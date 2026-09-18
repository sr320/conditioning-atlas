#!/usr/bin/env bash
# Phase 1, step 2: BUSCO (metazoa_odb10) on every assembly in genomics/data/manifest.tsv.
#
# Proteins mode where NCBI supplied a proteome (minutes), genome mode otherwise
# (hours; metaeuk). One lineage for every species so scores are comparable;
# NCBI's own BUSCO numbers use per-clade lineages and are collected separately.
#
# Usage:  THREADS=16 bash genomics/run_busco.sh
# Output: genomics/results/busco/<ACC>/short_summary.*.json  (skipped if present)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST="$HERE/data/manifest.tsv"
OUT="$HERE/results/busco"
THREADS="${THREADS:-8}"
LINEAGE="${LINEAGE:-metazoa_odb10}"

command -v busco >/dev/null || { echo "busco not on PATH; activate the conda env" >&2; exit 1; }
[[ -f "$MANIFEST" ]] || { echo "missing $MANIFEST; run fetch_assemblies.py first" >&2; exit 1; }
mkdir -p "$OUT"

tail -n +2 "$MANIFEST" | while IFS=$'\t' read -r species acc genome protein gff proteome_url notes; do
  [[ -n "$acc" ]] || { echo "skip $species (no accession)"; continue; }
  if compgen -G "$OUT/$acc/short_summary.*.json" >/dev/null; then
    echo "= $acc done"; continue
  fi
  if [[ -n "$protein" && -s "$protein" ]]; then
    mode=proteins; input="$protein"
  elif [[ -n "$proteome_url" && "$proteome_url" != "" ]]; then
    echo "!! $species: proteome override URL set but not fetched; fetch it to data/$acc/override.faa and rerun" >&2
    mode=genome; input="$genome"
  else
    mode=genome; input="$genome"
  fi
  echo "+ busco $acc ($species) mode=$mode"
  busco -i "$input" -m "$mode" -l "$LINEAGE" -c "$THREADS" -o "$acc" --out_path "$OUT" -f
done
echo "BUSCO complete; now: python3 genomics/collect_derived.py --from-ncbi --from-busco $OUT"
