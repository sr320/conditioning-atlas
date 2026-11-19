"""Shared helpers for the weekly literature sweep (see WEEKLY_SWEEP_PLAN.md)."""
from __future__ import annotations

import csv
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "sweep_runs"
STATE = ROOT / "sweep_state"

CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "")
USER_AGENT = "conditioning-atlas-sweep/0.1 (https://github.com/sr320/conditioning-atlas" + (
    f"; mailto:{CONTACT_EMAIL})" if CONTACT_EMAIL else ")")

DOI_RE = re.compile(r"10\.\d{4,9}/\S+", re.I)


def norm_doi(s: str | None) -> str:
    """Bare, lower-case DOI, or '' if none."""
    if not s:
        return ""
    m = DOI_RE.search(s.strip())
    return m.group(0).rstrip(".;,").lower() if m else ""


def _read(path: str, ref: str | None) -> str:
    """File contents from the working tree, or from a git ref when given."""
    if ref is None:
        p = ROOT / path
        return p.read_text(encoding="utf-8") if p.exists() else ""
    r = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=ROOT,
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def _ls(pattern: str, ref: str | None) -> list[str]:
    if ref is None:
        return sorted(p.name for p in ROOT.glob(pattern))
    r = subprocess.run(["git", "ls-tree", "--name-only", ref], cwd=ROOT,
                       capture_output=True, text=True, check=True)
    rx = re.compile("^" + pattern.replace(".", r"\.").replace("*", ".*") + "$")
    return sorted(n for n in r.stdout.split() if rx.match(n))


def known_dois(ref: str | None = None) -> dict[str, str]:
    """Every DOI the atlas already knows about -> where it is recorded.

    Reads rows_*.tsv (column 2), excluded_*.tsv (column 1), pending_review.tsv
    and sweep_state/seen.tsv. With `ref`, reads them as of that git commit,
    which is how the backtest reproduces the state before a past sweep.
    """
    known: dict[str, str] = {}
    for name in _ls("rows_*.tsv", ref):
        for line in _read(name, ref).splitlines():
            f = line.split("\t")
            if len(f) > 1 and norm_doi(f[1]):
                known.setdefault(norm_doi(f[1]), name)
    for name in _ls("excluded_*.tsv", ref):
        for line in _read(name, ref).splitlines():
            d = norm_doi(line.split("\t")[0])
            if d:
                known.setdefault(d, name)
    for name in ("pending_review.tsv", "sweep_state/seen.tsv"):
        for row in csv.DictReader(_read(name, ref).splitlines(), delimiter="\t"):
            d = norm_doi(row.get("doi"))
            if d:
                known.setdefault(d, name)
    return known


def write_jsonl(path: Path, records) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
