#!/usr/bin/env python3
"""Build the deployable Magil artifacts from the staging integration.

Produces (committed, git-tracked):
  data/contextual_noach.json     wid -> {contextual, flagged, note, ...}  (Magil)
  data/suggestions_noach.json    wid -> [chips]  (Magil base first; Etheridge dropped)
  data/selfcheck_noach.json      wid -> {confidence, check_results}  (Magil re-score)
  app/static/magil_ref.json      ref -> {leaf, page_url, spans:[...]}   (views + page image)

Compliance: the forbidden Etheridge English Onkelos chip is removed. The fact
that Onkelos recasts a pasuk survives only as a neutral confidence note (no
Etheridge text). Rashi chips are Rosenbaum-Silbermann (PD Genesis, allowed).
"""
import json, os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STG = os.path.join(ROOT, "data", "staging")
def L(p): return json.load(open(p, encoding="utf-8-sig"))
def Wj(p, o): json.dump(o, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

IA = "magilslinearscho00magirich"
def page_url(leaf):
    return f"https://archive.org/download/{IA}/page/n{leaf}_medium.jpg" if leaf else None

lw = L(os.path.join(STG, "live_words.json"))
id2 = {w["id"]: w for w in lw}
perword = {int(k): v for k, v in L(os.path.join(STG, "magil_perword.json")).items()}
spans_by_cv = L(os.path.join(STG, "magil_spans_by_cv.json"))
selfcheck = L(os.path.join(STG, "selfcheck_magil.json"))
sugg_old = L(os.path.join(STG, "suggestions_map.json"))

FORBIDDEN = {"Onkelos (Etheridge, per pasuk)"}   # Etheridge English — never ship
CHIP_ORDER = ["Binyan", "Rashi", "Root gloss", "Morphology (morphhb)"]
def order_key(lbl):
    for i, pref in enumerate(CHIP_ORDER):
        if lbl.startswith(pref):
            return i
    return len(CHIP_ORDER)

# ---- contextual + suggestions + selfcheck (wid-keyed) ----
contextual, suggestions = {}, {}
etheridge_dropped = 0
for w in lw:
    wid = w["id"]; pw = perword.get(wid, {})
    ctx = pw.get("contextual")
    contextual[str(wid)] = {
        "contextual": ctx, "flagged": False,
        "note": (pw.get("note") or ""), "ref": w["ref"], "pos": w["pos"],
        "he": w["he"], "gloss": w["tr"],
    }
    chips = []
    if ctx:
        chips.append({"source_label": "Magil (linear, 1905)", "text": ctx,
                      "recast": False, "base": True, "supplied": pw.get("supplied", False)})
    if pw.get("literal"):
        chips.append({"source_label": "Magil literal (H.)", "text": pw["literal"], "recast": False})
    kept = []
    for o in sugg_old.get(str(wid), []):
        if o.get("source_label") in FORBIDDEN:
            etheridge_dropped += 1
            continue
        kept.append({k: v for k, v in o.items() if k != "recast"} | {"recast": False})
    kept.sort(key=lambda o: order_key(o.get("source_label", "")))
    suggestions[str(wid)] = chips + kept

Wj(os.path.join(ROOT, "data", "contextual_noach.json"), contextual)
Wj(os.path.join(ROOT, "data", "suggestions_noach.json"), suggestions)
Wj(os.path.join(ROOT, "data", "selfcheck_noach.json"), selfcheck)

# ---- static per-ref span + page file (positions, environment-independent) ----
ref_out = {}
for cv, spans in spans_by_cv.items():
    ref = id2[spans[0]["wids"][0]]["ref"] if spans else f"Bereishis {cv}"
    leaf = perword.get(spans[0]["wids"][0], {}).get("leaf") if spans else None
    out_spans = []
    for sp in spans:
        positions = [id2[wid]["pos"] for wid in sp["wids"] if wid in id2]
        out_spans.append({
            "en": sp["en"], "en_tokens": sp.get("en_tokens"),
            "positions": positions, "kind": sp["kind"],
            "supplied": sp["supplied"], "literal": sp.get("literal"),
            "note": sp.get("note"),
        })
    ref_out[ref] = {"leaf": leaf, "page_url": page_url(leaf), "spans": out_spans}

Wj(os.path.join(ROOT, "app", "static", "magil_ref.json"), ref_out)

# ---- report ----
from collections import Counter
dist = Counter(v["confidence"] for v in selfcheck.values())
nchips = Counter()
for chips in suggestions.values():
    for c in chips:
        nchips[c["source_label"].split(":")[0]] += 1
print("BUILD MAGIL RELEASE")
print(f"  words: {len(lw)}   refs: {len(ref_out)}")
print(f"  Etheridge chips dropped: {etheridge_dropped}")
print(f"  confidence: {dict(dist)}")
print(f"  chip counts: {dict(nchips)}")
print(f"  contextual filled: {sum(1 for c in contextual.values() if c['contextual'])}")
print(f"  static file: app/static/magil_ref.json ({len(ref_out)} pesukim, page_url per pasuk)")
