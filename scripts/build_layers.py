#!/usr/bin/env python3
"""Layer 1 (Shoresh / root) clean reseed. Map each Noach word's morphhb lemma
(Strong's number) to a CLEAN primary sense from Strong's Hebrew Dictionary
(James Strong, 1890 — public domain; markup via OpenScriptures HebrewLexicon).
Take the first <def> as the field value; the remaining <def>s become
'other senses' chips. This replaces the KJV-usage dumps ('cruel-ty, damage')
with the primary sense ('violence').

Outputs (committed):
  data/root_gloss_noach.json   wid -> {root_gloss, senses:[alternates], strongs}
"""
import json, os, re, xml.etree.ElementTree as ET
from collections import defaultdict, Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STG = os.path.join(ROOT, "data", "staging")
SCRATCH = r"C:\Users\RGBY\AppData\Local\Temp\claude\F--\358f8128-a2d1-49ad-8b08-206f9ba52342\scratchpad"
NS = "{http://www.bibletechnologies.net/2003/OSIS/namespace}"
def L(p): return json.load(open(p, encoding="utf-8-sig"))

# --- Strong's lexicon: strongs number -> ordered list of primary senses ---
lex = open(os.path.join(SCRATCH, "HebrewStrong.xml"), encoding="utf-8").read()
defs = {}
for m in re.finditer(r'<entry id="H(\d+)">(.*?)</entry>', lex, re.S):
    num, body = m.group(1), m.group(2)
    mean = re.search(r"<meaning>(.*?)</meaning>", body, re.S)
    if not mean:
        continue
    ds = [re.sub(r"<[^>]+>", "", d).strip()
          for d in re.findall(r"<def>(.*?)</def>", mean.group(1), re.S)]
    ds = [d for d in ds if d]
    if ds:
        defs[num] = ds

# --- morphhb Noach: word (in order) -> lemma strongs ---
tree = ET.parse(os.path.join(STG, "morphhb_Gen.xml"))
heb_by_cv = defaultdict(list)
for v in tree.getroot().iter(NS + "verse"):
    oid = v.get("osisID")
    if not oid: continue
    _, c, vs = oid.split("."); c = int(c); vs = int(vs)
    if not ((c == 6 and vs >= 9) or (7 <= c <= 10) or (c == 11 and vs <= 32)):
        continue
    for w in v.iter(NS + "w"):
        heb_by_cv[f"{c}:{vs}"].append(w.get("lemma", ""))

def strongs_of(lemma):
    # "b/7225" -> 7225 ; "1254 a" -> 1254 ; "853" -> 853 ; take the last numeric run
    nums = re.findall(r"\d+", lemma or "")
    return nums[-1] if nums else None

# --- align to live words, build clean root gloss ---
lw = L(os.path.join(STG, "live_words.json"))
by_cv = defaultdict(list)
for w in lw:
    by_cv[w["ref"].split()[-1]].append(w)
for cv in by_cv:
    by_cv[cv].sort(key=lambda w: w["pos"])

out = {}
clean = fallback = kept_existing = from_strongs = 0
multi_before = 0
JUNK = re.compile(r"[,;]|\+|\bX\b|\d")
for cv, words in by_cv.items():
    lemmas = heb_by_cv.get(cv, [])
    for i, w in enumerate(words):
        lemma = lemmas[i] if i < len(lemmas) else ""
        num = strongs_of(lemma)
        senses = defs.get(num, [])
        tr = (w["tr"] or "").strip()
        is_junk = bool(JUNK.search(tr))
        if is_junk:
            multi_before += 1
        # Keep the existing gloss when it is already a clean single sense (those
        # are the right common meanings — "generation", "flesh"); only fall back
        # to Strong's primary for the junk multi-sense dumps. Strong's senses
        # are offered as chips either way.
        if tr and not is_junk:
            root = tr; from_lex = False
        elif senses:
            root = senses[0]; from_lex = True
        else:
            root = None; from_lex = None
        chips = [s for s in senses if s != root][:5]
        out[str(w["id"])] = {"root_gloss": root, "senses": chips, "strongs": num}
        if root:
            clean += 1
            if from_lex: from_strongs += 1
            else: kept_existing += 1
        else:
            fallback += 1

json.dump(out, open(os.path.join(ROOT, "data", "root_gloss_noach.json"), "w",
                    encoding="utf-8"), ensure_ascii=False, indent=1)

# --- clean the suggestion chips: replace junk "Root gloss" chip with the
#     Strong's primary sense; add alternate senses as chips (not the field) ---
sugg_path = os.path.join(ROOT, "data", "suggestions_noach.json")
sugg = json.load(open(sugg_path, encoding="utf-8-sig"))
chips_added = 0
for wid, rec in out.items():
    chips = sugg.get(wid, [])
    chips = [c for c in chips if c.get("source_label") not in
             ("Root gloss", "Shoresh (Strong's primary)", "Shoresh (root)", "Other sense (Strong's)")]
    if rec["root_gloss"]:
        at = 1 if chips and chips[0].get("base") else 0
        chips.insert(at, {"source_label": "Shoresh (root)",
                          "text": rec["root_gloss"], "recast": False})
        for s in rec["senses"][:4]:
            chips.append({"source_label": "Other sense (Strong's)", "text": s, "recast": False})
            chips_added += 1
    sugg[wid] = chips
json.dump(sugg, open(sugg_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"  suggestion chips: root-sense set on {sum(1 for v in out.values() if v['root_gloss'])} words, "
      f"{chips_added} alternate-sense chips added")

# how many of the previously-junk words now get a clean primary
prev_junk_fixed = 0
for w in lw:
    if JUNK.search(w["tr"] or "") and out[str(w["id"])]["root_gloss"] and not JUNK.search(out[str(w["id"])]["root_gloss"]):
        prev_junk_fixed += 1

print("LAYER 1 (Shoresh) CLEAN RESEED")
print(f"  Strong's entries with defs: {len(defs)}")
print(f"  words total: {len(lw)}")
print(f"  clean single-sense shoresh : {clean}  (kept existing clean gloss: {kept_existing}, "
      f"relexed from Strong's: {from_strongs})")
print(f"  fallback (no lexicon entry, e.g. את/name): {fallback}")
print(f"  words with alternate senses (-> chips): {sum(1 for v in out.values() if v['senses'])}")
print(f"  --- vs the old junk ---")
print(f"  previously-junk glosses (multi-sense): {multi_before}")
print(f"  of those, now a clean single sense   : {prev_junk_fixed}")
# samples
print("  samples (previously junk -> clean primary):")
shown = 0
for w in lw:
    if JUNK.search(w["tr"] or "") and out[str(w["id"])]["root_gloss"]:
        print(f"    {w['he']}  {w['tr']!r} -> {out[str(w['id'])]['root_gloss']!r}  (alt: {out[str(w['id'])]['senses'][:2]})")
        shown += 1
        if shown >= 10: break
