#!/usr/bin/env python3
"""Cache Jastrow locally for Onkelos-Noach — same move as the Magil scans:
stop depending on the round-trip. Sweeps every unique Aramaic surface form
(plus prefix-stripped variants), keeps only JASTROW entries (PD, London,
Luzac, 1903 — version verified in-body on Sefaria), resolves 'v. X'
cross-references AT BUILD TIME, strips Sefaria's internal <a> links (keeping
their text), and writes app/static/jastrow_noach.json for instant, offline
lookups. Entries stay as Jastrow printed them; the panel still fills nothing.
"""
import json, re, urllib.request, urllib.parse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parent.parent
onk = json.loads((ROOT/"data"/"onkelos_noach.json").read_text(encoding="utf-8-sig"))

NIKUD = re.compile(r"[֑-ׇ]")
def clean(w): return NIKUD.sub("", w).strip("׃־:,.")

words = set()
for txt in onk.values():
    for w in (txt or "").split():
        c = clean(w)
        if len(c) >= 2: words.add(c)
print(f"unique Aramaic surface forms: {len(words)}")

def variants(w):
    out = [w]
    if re.match(r"^[ובדלכמש]", w) and len(w) > 2: out.append(w[1:])
    if re.match(r"^[וב][דלכמש]", w) and len(w) > 3: out.append(w[2:])
    return out

def fetch(form):
    url = "https://www.sefaria.org/api/words/" + urllib.parse.quote(form)
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return form, json.loads(r.read().decode())
    except Exception:
        return form, []

# pass 1: all variants of all words
todo = sorted({v for w in words for v in variants(w)})
print(f"forms to query: {len(todo)}")
results = {}
with ThreadPoolExecutor(max_workers=10) as ex:
    for form, data in ex.map(fetch, todo):
        results[form] = data

LINK = re.compile(r"<a[^>]*>(.*?)</a>", re.S)
def strip_links(h): return LINK.sub(r"\1", h or "")

def jastrow_entries(data):
    out = []
    for e in data or []:
        if "Jastrow" not in (e.get("parent_lexicon") or ""): continue
        senses = " ".join(s.get("definition") or "" for s in
                          (e.get("content") or {}).get("senses") or [])
        out.append({"hw": e.get("headword") or "", "def": strip_links(senses)})
    return out

XREF = re.compile(r"(?:^|[\s(])(?:v\.|cmp\.)\s+([֐-׿][֐-׿ְ-ׇ]*)")
# pass 2: cross-reference targets not already fetched
targets = set()
for data in results.values():
    for e in jastrow_entries(data):
        plain = re.sub(r"<[^>]+>", " ", e["def"])
        if len(plain.strip()) < 120:
            m = XREF.search(plain)
            if m:
                t = NIKUD.sub("", m.group(1))
                if t not in results: targets.add(t)
print(f"cross-reference targets to fetch: {len(targets)}")
with ThreadPoolExecutor(max_workers=10) as ex:
    for form, data in ex.map(fetch, sorted(targets)):
        results[form] = data

cache = {}
followed = 0
for w in sorted(words):
    hits, seen = [], set()
    for v in variants(w):
        for e in jastrow_entries(results.get(v)):
            if e["hw"] in seen: continue
            seen.add(e["hw"])
            hits.append(dict(e, via=v if v != w else None))
            plain = re.sub(r"<[^>]+>", " ", e["def"])
            if len(plain.strip()) < 120:
                m = XREF.search(plain)
                if m:
                    t = NIKUD.sub("", m.group(1))
                    for te in jastrow_entries(results.get(t)):
                        if te["hw"] not in seen:
                            seen.add(te["hw"])
                            hits.append(dict(te, via=f"xref:{e['hw']}"))
                            followed += 1
    if hits: cache[w] = hits

(ROOT/"app"/"static"/"jastrow_noach.json").write_text(
    json.dumps(cache, ensure_ascii=False), encoding="utf-8")
none = len(words) - len(cache)
print(f"COVERAGE: {len(cache)}/{len(words)} surface forms got >=1 Jastrow entry")
print(f"  no entry (dead-end): {none}")
print(f"  cross-references followed & resolved: {followed}")
print(f"  multi-candidate forms: {sum(1 for v in cache.values() if len(v) > 1)}")
import os
print(f"  cache size: {os.path.getsize(ROOT/'app'/'static'/'jastrow_noach.json')//1024} KB")
