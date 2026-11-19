#!/usr/bin/env python3
"""Step 1-2 of the weekly sweep: find candidate papers and drop known ones.

Queries Europe PMC (by index date; covers PubMed and the preprint servers),
PubMed (by create date) and OpenAlex (by publication date; its index-date
filter needs a paid plan) with the blocks in sweep/queries.yaml, merges hits
by DOI, applies the same blocks locally as a prefilter, and removes every DOI
the atlas already records.

    python -m sweep.discover --since 2026-06-01 --until 2026-10-25 --run-id backtest-2026-10
    python -m sweep.discover --since 2026-06-01 --until 2026-10-25 --known-ref fc079b3^

Writes sweep_runs/<run_id>/: hits.jsonl (every merged hit), candidates.jsonl
(prefiltered and new; the input to screen.py) and discover_summary.json.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET

import httpx
import yaml

from sweep.common import RUNS, ROOT, USER_AGENT, CONTACT_EMAIL, known_dois, norm_doi, read_jsonl, write_jsonl

EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
OPENALEX = "https://api.openalex.org/works"


def load_queries() -> dict:
    return yaml.safe_load((ROOT / "sweep" / "queries.yaml").read_text(encoding="utf-8"))


def term_regex(terms: list[str]) -> re.Pattern:
    parts = []
    for t in terms:
        body = re.escape(t[:-1] if t.endswith("*") else t).replace(r"\ ", r"[\s-]+").replace(r"\-", r"[\s-]?")
        parts.append(r"\b" + body + (r"\w*" if t.endswith("*") else r"\b"))
    return re.compile("|".join(parts), re.I)


def clean(s: str | None) -> str:
    s = html.unescape(s or "")
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip()


def client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=60, follow_redirects=True)


def get(c: httpx.Client, url: str, *, tries: int = 4, method: str = "GET", **kw) -> httpx.Response:
    for i in range(tries):
        try:
            r = c.request(method, url, **kw)
            if r.status_code in (429, 500, 502, 503, 504):
                raise httpx.HTTPStatusError("retryable", request=r.request, response=r)
            r.raise_for_status()
            return r
        except (httpx.HTTPStatusError, httpx.TransportError) as e:
            if i == tries - 1:
                raise
            time.sleep(2 ** i * 2)
    raise RuntimeError("unreachable")


# --- Europe PMC ----------------------------------------------------------------

def epmc_block(terms: list[str]) -> str:
    q = [f'"{t}"' if " " in t or "-" in t else t for t in terms]
    return "(" + " OR ".join(f"TITLE_ABS:{t}" for t in q) + ")"


def search_europepmc(c, q, since, until, max_n) -> list[dict]:
    query = (f"{epmc_block(q['conditioning'])} AND {epmc_block(q['taxon'])} "
             f"AND FIRST_IDATE:[{since} TO {until}]")
    out, cursor = [], "*"
    while len(out) < max_n:
        r = get(c, EPMC + "POST", method="POST", data={
            "query": query, "format": "json", "resultType": "core",
            "pageSize": 1000, "cursorMark": cursor})
        d = r.json()
        for w in d["resultList"]["result"]:
            out.append({
                "doi": norm_doi(w.get("doi")),
                "title": clean(w.get("title")),
                "abstract": clean(w.get("abstractText")),
                "journal": clean((w.get("journalInfo") or {}).get("journal", {}).get("title")
                                 or (w.get("bookOrReportDetails") or {}).get("publisher")),
                "year": w.get("pubYear", ""),
                "first_author": clean(((w.get("authorList") or {}).get("author") or [{}])[0].get("lastName")),
                "pmid": w.get("pmid", ""),
                "pmcid": w.get("pmcid", ""),
                "is_preprint": w.get("source") == "PPR",
                "index_date": w.get("firstIndexDate", ""),
                "pub_date": w.get("firstPublicationDate", ""),
                "source": "europepmc",
            })
        nxt = d.get("nextCursorMark")
        if not nxt or nxt == cursor or not d["resultList"]["result"]:
            break
        cursor = nxt
    print(f"  europepmc: {d.get('hitCount')} hits, fetched {len(out)}", file=sys.stderr)
    return out[:max_n]


# --- PubMed ------------------------------------------------------------------

def pubmed_block(terms: list[str]) -> str:
    return "(" + " OR ".join(f'"{t}"[tiab]' if "*" not in t else f"{t}[tiab]" for t in terms) + ")"


def search_pubmed(c, q, since, until, max_n) -> list[dict]:
    a, b = since.replace("-", "/"), until.replace("-", "/")
    term = f'{pubmed_block(q["conditioning"])} AND {pubmed_block(q["taxon"])} AND ("{a}"[crdt] : "{b}"[crdt])'
    r = get(c, f"{EUTILS}/esearch.fcgi", method="POST", data={
        "db": "pubmed", "term": term, "retmax": max_n, "retmode": "json", "usehistory": "n"})
    ids = r.json()["esearchresult"].get("idlist", [])
    print(f"  pubmed: {r.json()['esearchresult'].get('count')} hits, fetched {len(ids)}", file=sys.stderr)
    out = []
    for i in range(0, len(ids), 200):
        x = get(c, f"{EUTILS}/efetch.fcgi", method="POST",
                data={"db": "pubmed", "id": ",".join(ids[i:i + 200]), "retmode": "xml"})
        for art in ET.fromstring(x.content).iter("PubmedArticle"):
            # Only the article's own ID list: art.iter("ArticleId") would also walk the
            # ReferenceList and return a cited paper's DOI.
            ids_ = {e.get("IdType"): (e.text or "") for e in art.findall("PubmedData/ArticleIdList/ArticleId")}
            abst = " ".join("".join(e.itertext()) for e in art.iter("AbstractText"))
            last = art.find(".//AuthorList/Author/LastName")
            out.append({
                "doi": norm_doi(ids_.get("doi")),
                "title": clean("".join(art.find(".//ArticleTitle").itertext())),
                "abstract": clean(abst),
                "journal": clean(art.findtext(".//Journal/Title")),
                "year": art.findtext(".//PubDate/Year") or "",
                "first_author": clean(last.text if last is not None else ""),
                "pmid": ids_.get("pubmed", ""),
                "pmcid": ids_.get("pmc", ""),
                "is_preprint": False,
                "index_date": "",
                "pub_date": "",
                "source": "pubmed",
            })
        time.sleep(0.4)
    return out


# --- OpenAlex -----------------------------------------------------------------

def openalex_block(terms: list[str]) -> str:
    return "(" + " OR ".join(f'"{t.rstrip("*")}"' for t in terms) + ")"


def inverted_to_text(inv) -> str:
    if not inv:
        return ""
    pos = sorted((i, w) for w, idx in inv.items() for i in idx)
    return " ".join(w for _, w in pos)


def search_openalex(c, q, since, until, max_n) -> list[dict]:
    # title_and_abstract.search, not search=: the latter also matches full text
    # (15k hits for Jan-Oct 2026 vs a few hundred). Publication date, not
    # created date: the created_date filter needs a paid OpenAlex plan.
    s = f"{openalex_block(q['conditioning'])} AND {openalex_block(q['taxon'])}"
    params = {
        "filter": f"title_and_abstract.search:{s},from_publication_date:{since},"
                  f"to_publication_date:{until},type:article|preprint",
        "per-page": 200,
        "select": "doi,title,publication_year,publication_date,authorships,abstract_inverted_index,"
                  "primary_location,ids,type",
    }
    if CONTACT_EMAIL:
        params["mailto"] = CONTACT_EMAIL
    if os.environ.get("OPENALEX_API_KEY"):
        params["api_key"] = os.environ["OPENALEX_API_KEY"]
    out, cursor, total = [], "*", None
    while len(out) < max_n and cursor:
        params["cursor"] = cursor
        try:
            d = get(c, OPENALEX, params=params).json()
        except httpx.HTTPStatusError as e:
            # Without a key OpenAlex shares a $0.10/day budget per IP; keep what we have.
            print(f"  openalex: stopped after {len(out)} ({e.response.status_code})", file=sys.stderr)
            break
        total = (d.get("meta") or {}).get("count")
        for w in d.get("results", []):
            loc = w.get("primary_location") or {}
            src = loc.get("source") or {}
            auth = (w.get("authorships") or [{}])[0].get("author") or {}
            ids = w.get("ids") or {}
            out.append({
                "doi": norm_doi(w.get("doi")),
                "title": clean(w.get("title")),
                "abstract": clean(inverted_to_text(w.get("abstract_inverted_index"))),
                "journal": clean(src.get("display_name")),
                "year": str(w.get("publication_year") or ""),
                "first_author": (auth.get("display_name") or "").split(" ")[-1],
                "pmid": (ids.get("pmid") or "").rsplit("/", 1)[-1],
                "pmcid": (ids.get("pmcid") or "").rsplit("/", 1)[-1],
                "is_preprint": w.get("type") == "preprint",
                "index_date": "",
                "pub_date": w.get("publication_date", ""),
                "source": "openalex",
            })
        cursor = (d.get("meta") or {}).get("next_cursor")
        if not d.get("results"):
            break
        time.sleep(1)
    print(f"  openalex: {total} hits, fetched {len(out)}", file=sys.stderr)
    return out[:max_n]


def fill_missing_dois(c, hits: list[dict]) -> None:
    """Europe PMC returns some PMC-sourced records without a DOI; recover it
    from the PMCID/PMID through the NCBI ID converter so dedupe can work."""
    # The converter rejects a request that mixes PMCIDs and PMIDs, so batch each kind separately.
    no_doi = [h for h in hits if not h["doi"]]
    groups = [[h for h in no_doi if h.get("pmcid")],
              [h for h in no_doi if not h.get("pmcid") and h.get("pmid")]]
    chunks = [g[i:i + 150] for g in groups for i in range(0, len(g), 150)]
    for chunk in chunks:
        ids = ",".join(h.get("pmcid") or h["pmid"] for h in chunk)
        p = {"ids": ids, "format": "json", "tool": "conditioning-atlas"}
        if CONTACT_EMAIL:  # a placeholder email gets a 400
            p["email"] = CONTACT_EMAIL
        try:
            recs = get(c, "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/",
                       params=p).json().get("records", [])
        except Exception as e:
            print(f"  idconv failed: {e}", file=sys.stderr)
            return
        by = {}
        for r in recs:
            for k in ("pmcid", "pmid"):
                if r.get(k):
                    by[str(r[k])] = norm_doi(r.get("doi"))
        for h in chunk:
            h["doi"] = by.get(h.get("pmcid") or "", "") or by.get(h.get("pmid") or "", "")


# --- merge -------------------------------------------------------------------

def merge(hits: list[dict]) -> list[dict]:
    """One record per DOI (or per normalised title when no DOI), keeping the
    longest abstract and every source that returned it."""
    by: dict[str, dict] = {}
    for h in hits:
        key = h["doi"] or "title:" + re.sub(r"[^a-z0-9]", "", h["title"].lower())[:80]
        if key not in by:
            by[key] = {**h, "sources": [h["source"]]}
            by[key].pop("source")
            continue
        m = by[key]
        if h["source"] not in m["sources"]:
            m["sources"].append(h["source"])
        for k, v in h.items():
            if k == "source":
                continue
            if k == "abstract" and len(v) > len(m.get(k) or ""):
                m[k] = v
            elif not m.get(k) and v:
                m[k] = v
    return list(by.values())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    today = dt.date.today()
    ap.add_argument("--since", default=str(today - dt.timedelta(days=14)))
    ap.add_argument("--until", default=str(today))
    ap.add_argument("--run-id", default=f"{today.isocalendar()[0]}-W{today.isocalendar()[1]:02d}")
    ap.add_argument("--sources", default="europepmc,pubmed,openalex")
    ap.add_argument("--known-ref", default=None,
                    help="git ref whose source files define 'already known' (backtests)")
    ap.add_argument("--reuse", default="",
                    help="comma-separated sources to load from this run's raw_<source>.jsonl instead of querying")
    a = ap.parse_args()

    q = load_queries()
    lim = q.get("limits", {})
    run = RUNS / a.run_id
    hits: list[dict] = []
    per_source: dict[str, int] = {}
    fns = {"europepmc": (search_europepmc, lim.get("europepmc_max", 3000)),
           "pubmed": (search_pubmed, lim.get("pubmed_max", 3000)),
           "openalex": (search_openalex, lim.get("openalex_max", 1500))}
    reuse = set(filter(None, a.reuse.split(",")))
    with client() as c:
        for s in a.sources.split(","):
            raw = run / f"raw_{s}.jsonl"
            if s in reuse and raw.exists():
                got = read_jsonl(raw)
                print(f"  {s}: reused {len(got)} cached hits", file=sys.stderr)
            else:
                fn, n = fns[s]
                try:
                    got = fn(c, q, a.since, a.until, n)
                except Exception as e:  # one failing source must not sink the run
                    print(f"  {s}: FAILED {e}", file=sys.stderr)
                    got = []
                write_jsonl(raw, got)
            per_source[s] = len(got)
            hits += got
        fill_missing_dois(c, hits)

    merged = merge(hits)
    cond, tax = term_regex(q["conditioning"]), term_regex(q["taxon"])
    known = known_dois(a.known_ref)

    candidates, n_prefilter_drop, n_known = [], 0, 0
    for m in merged:
        text = f"{m['title']} {m['abstract']}"
        m["prefilter"] = bool(cond.search(text) and tax.search(text))
        m["known_in"] = known.get(m["doi"], "")
        if not m["prefilter"]:
            n_prefilter_drop += 1
        elif m["known_in"]:
            n_known += 1
        else:
            candidates.append(m)

    write_jsonl(run / "hits.jsonl", merged)
    write_jsonl(run / "candidates.jsonl", candidates)
    summary = {
        "run_id": a.run_id, "since": a.since, "until": a.until, "known_ref": a.known_ref,
        "per_source": per_source, "merged": len(merged),
        "dropped_prefilter": n_prefilter_drop, "dropped_known": n_known,
        "candidates": len(candidates),
        "candidates_without_abstract": sum(1 for x in candidates if not x["abstract"]),
    }
    (run / "discover_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
