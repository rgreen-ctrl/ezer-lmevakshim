#!/usr/bin/env python3
"""Build per-pasuk Onkelos (Aramaic) + Rashi (Hebrew + R-S English) reference
data for Noach from the Sefaria raw dump. All versions are PUBLIC DOMAIN
(verified at fetch and re-asserted here). Onkelos is whole-pasuk; Rashi is a
list of comments per pasuk, each with its דיבור המתחיל split out.

Outputs (committed):
  data/onkelos_noach.json          ref -> aramaic
  data/rashi_noach.json            ref -> [ {dh, he, en} ]
  app/static/sources_noach.json    ref -> {onkelos, rashi:[...]}  (Desk pasuk panel)
"""
import json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRATCH = r"C:\Users\RGBY\AppData\Local\Temp\claude\F--\358f8128-a2d1-49ad-8b08-206f9ba52342\scratchpad"
raw = json.load(open(os.path.join(SCRATCH, "sefaria_raw.json"), encoding="utf-8-sig"))

# hard re-assert: every source version is Public Domain
for k, v in raw["licenses"].items():
    assert v.startswith("Public Domain"), f"NON-PD source slipped through: {k} = {v}"

NOACH = {6: range(9, 23), 7: range(1, 25), 8: range(1, 23),
         9: range(1, 30), 10: range(1, 33), 11: range(1, 33)}

def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()

def split_dh(he_comment):
    """First <b>…</b> is the דיבור המתחיל; the rest is the comment body."""
    m = re.search(r"<b>(.*?)</b>", he_comment or "", re.S)
    dh = strip_tags(m.group(1)) if m else ""
    body = strip_tags(re.sub(r"<b>.*?</b>", "", he_comment or "", count=1, flags=re.S))
    return dh, body

def verse(arr, v):
    return arr[v - 1] if arr and (v - 1) < len(arr) else None

onkelos, rashi, sources = {}, {}, {}
cov = {"onkelos": 0, "rashi": 0, "both": 0, "neither": [], "onkelos_only": [], "rashi_only": []}

for ch, verses in NOACH.items():
    o_arr = raw["onkelos"].get(str(ch), [])
    rh_arr = raw["rashi_he"].get(str(ch), [])
    re_arr = raw["rashi_en"].get(str(ch), [])
    for v in verses:
        ref = f"Bereishis {ch}:{v}"
        ono = verse(o_arr, v)
        ono = strip_tags(ono) if isinstance(ono, str) and strip_tags(ono) else None
        he_comments = verse(rh_arr, v) or []
        en_comments = verse(re_arr, v) or []
        comments = []
        for i, hc in enumerate(he_comments):
            dh, body = split_dh(hc)
            en = strip_tags(en_comments[i]) if i < len(en_comments) else None
            comments.append({"dh": dh, "he": body, "en": en or None})
        if ono:
            onkelos[ref] = ono
        if comments:
            rashi[ref] = comments
        sources[ref] = {"onkelos": ono, "rashi": comments}
        has_o, has_r = bool(ono), bool(comments)
        cov["onkelos"] += has_o; cov["rashi"] += has_r
        if has_o and has_r: cov["both"] += 1
        elif has_o: cov["onkelos_only"].append(ref)
        elif has_r: cov["rashi_only"].append(ref)
        else: cov["neither"].append(ref)

def W(p, o): json.dump(o, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
W(os.path.join(ROOT, "data", "onkelos_noach.json"), onkelos)
W(os.path.join(ROOT, "data", "rashi_noach.json"), rashi)
W(os.path.join(ROOT, "app", "static", "sources_noach.json"), sources)

total = sum(len(list(r)) for r in NOACH.values())
print("BUILD SOURCES (Onkelos Aramaic + Rashi Hebrew/English, all PD)")
print(f"  pesukim total: {total}")
print(f"  with Onkelos Aramaic : {cov['onkelos']}")
print(f"  with Rashi (>=1 comment): {cov['rashi']}")
print(f"  with both: {cov['both']}")
print(f"  Onkelos only (no Rashi): {len(cov['onkelos_only'])}")
print(f"  Rashi only (no Onkelos): {len(cov['rashi_only'])}  {cov['rashi_only']}")
print(f"  neither: {len(cov['neither'])}  {cov['neither']}")
rc = sum(len(c) for c in rashi.values())
enc = sum(1 for cl in rashi.values() for c in cl if c['en'])
print(f"  total Rashi comments: {rc}; with R-S English: {enc}; Hebrew-only: {rc-enc}")
print(f"  6:9 sample onkelos: {onkelos.get('Bereishis 6:9','')[:60]}")
print(f"  6:9 rashi[0] dh: {rashi.get('Bereishis 6:9',[{}])[0].get('dh','')}")
