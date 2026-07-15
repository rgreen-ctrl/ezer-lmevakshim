#!/usr/bin/env python3
"""Phase 1 — span-assignment (span-centric). Build Magil spans over Hebrew word
positions. Proper-name + object-marker anchors force 1:1 where the counts
demand it; everything else becomes a faithful GROUPED span (one English phrase
shown across the Hebrew words it covers — exactly Magil's printed braces). A
grouped span is never split to per-word by guessing; it is marked split-pending.

Outputs (DRAFT, staging):
  magil_spans_by_cv.json  cv -> [ {en, wids[], kind, supplied, literal, note} ]
  magil_perword.json      word_id -> per-word record
  selfcheck_magil.json    word_id -> {confidence, check_results}
"""
import json, os, re, xml.etree.ElementTree as ET
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STG = os.path.join(ROOT, "data", "staging")
NS = "{http://www.bibletechnologies.net/2003/OSIS/namespace}"
def L(p): return json.load(open(p, encoding="utf-8-sig"))
def Wj(p, o): json.dump(o, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
SUP = re.compile(r"[\[\(…]")
def supplied(e): return e == "" or bool(SUP.search(e))

# Hebrew words with anchor flags
tree = ET.parse(os.path.join(STG, "morphhb_Gen.xml"))
heb = {}
for v in tree.getroot().iter(NS + "verse"):
    oid = v.get("osisID")
    if not oid: continue
    _, c, vs = oid.split("."); c = int(c); vs = int(vs)
    if not ((c == 6 and vs >= 9) or (7 <= c <= 10) or (c == 11 and vs <= 32)):
        continue
    lst = []
    for w in v.iter(NS + "w"):
        morph = w.get("morph", ""); lem = w.get("lemma", "")
        lst.append({"name": "Np" in morph,
                    "obj": morph == "HTo" or lem.split()[0] == "853"})
    heb[f"{c}:{vs}"] = lst

magil = L(os.path.join(STG, "magil_by_cv.json"))
lw = L(os.path.join(STG, "live_words.json"))
by_cv = defaultdict(list)
for w in lw:
    by_cv[w["ref"].split()[-1]].append(w)
for cv in by_cv:
    by_cv[cv].sort(key=lambda w: w["pos"])

STOP_CAP = {"And", "The", "These", "This", "Come", "Like", "Behold", "Or",
            "Therefore", "Get", "Of", "From", "In", "For", "He", "She", "I", "H"}
def is_name_tok(tok):
    return any(wd[0].isupper() and wd not in STOP_CAP
              for wd in re.findall(r"[A-Za-z']+", tok))

def name_segments(hlist, mlist):
    ha = [i for i, h in enumerate(hlist) if h["name"]]
    ma = [j for j, t in enumerate(mlist) if is_name_tok(t)]
    if len(ha) != len(ma):
        return None
    segs, ph, pm = [], 0, 0
    for hi, mj in zip(ha + [len(hlist)], ma + [len(mlist)]):
        segs.append(("run", list(range(ph, hi)), list(range(pm, mj))))
        if hi < len(hlist):
            segs.append(("anchor", [hi], [mj]))
        ph, pm = hi + 1, mj + 1
    return segs

spans_by_cv = {}
perword = {}
grouped_spans = 0
words_in_group = 0
confident_pesukim = 0

def foot_of(cv, idx):
    fn = magil[cv].get("footnotes", {}).get(str(idx)) if cv in magil else None
    if not fn: return (None, None)
    return (fn["text"] if fn.get("type") == "H" else None,
            fn["text"] if fn.get("type") in ("Or", "As") else None)

for cv, words in by_cv.items():
    hlist = heb[cv]; mlist = magil[cv]["contextual"] if cv in magil else []
    spans = []
    def add_span(en, wid_idxs, kind, midx=None):
        global grouped_spans, words_in_group
        wids = [words[i]["id"] for i in wid_idxs]
        lit = var = None
        if midx is not None and len(midx) == 1:
            lit, var = foot_of(cv, midx[0])
        toks = [mlist[j] for j in midx] if (kind == "grouped" and midx) else None
        if kind == "grouped":
            grouped_spans += 1; words_in_group += len(wids)
        spans.append({"en": en, "en_tokens": toks, "wids": wids, "kind": kind,
                      "supplied": supplied(en), "literal": lit, "note": var})

    if len(mlist) == len(hlist):
        for i in range(len(words)):
            add_span(mlist[i], [i], "1to1", [i])
        confident_pesukim += 1
    else:
        segs = name_segments(hlist, mlist)
        if segs is None:
            phrase = " ".join(t for t in mlist if t)
            add_span(phrase, list(range(len(words))), "grouped", list(range(len(mlist))))
        else:
            all_forced = True
            for tag, hidx, midx in segs:
                if not hidx and not midx:
                    continue
                if tag == "anchor":
                    add_span(mlist[midx[0]], hidx, "1to1", midx)
                    continue
                n_obj = sum(1 for i in hidx if hlist[i]["obj"])
                if len(midx) == len(hidx):
                    for k, i in enumerate(hidx):
                        add_span(mlist[midx[k]], [i], "1to1", [midx[k]])
                elif n_obj and len(midx) == len(hidx) - n_obj:
                    mi = 0
                    for i in hidx:
                        if hlist[i]["obj"]:
                            add_span("", [i], "1to1")           # את untranslated
                        else:
                            add_span(mlist[midx[mi]], [i], "1to1", [midx[mi]]); mi += 1
                else:
                    all_forced = False
                    phrase = " ".join(t for t in (mlist[j] for j in midx) if t)
                    add_span(phrase, hidx, "grouped", midx)
            if all_forced:
                confident_pesukim += 1
    spans_by_cv[cv] = spans
    for sp in spans:
        for wid in sp["wids"]:
            perword[wid] = {"contextual": sp["en"], "kind": sp["kind"],
                            "span_size": len(sp["wids"]), "supplied": sp["supplied"],
                            "literal": sp["literal"], "note": sp["note"],
                            "leaf": magil.get(cv, {}).get("leaf")}

Wj(os.path.join(STG, "magil_spans_by_cv.json"), spans_by_cv)
Wj(os.path.join(STG, "magil_perword.json"), perword)

# re-score
sugg = L(os.path.join(STG, "suggestions_map.json"))
def recast_on(wid): return any(o.get("recast") for o in sugg.get(str(wid), []))
selfcheck = {}; dist = Counter()
for w in lw:
    wid = w["id"]; pw = perword[wid]; checks = []
    if pw["kind"] == "grouped":
        conf = "medium"
        checks.append({"pass": 0, "level": "note",
                       "reason": f"Magil groups {pw['span_size']} Hebrew words under one phrase: '{pw['contextual']}' — phrase is correct; per-word split pending",
                       "proposed_fix": "split the grouped phrase to individual words (human eye)"})
    elif pw["contextual"] == "":
        conf = "medium"
        checks.append({"pass": 2, "level": "note",
                       "reason": "Magil leaves this word untranslated (object-marker את / structural)",
                       "proposed_fix": ""})
    elif recast_on(wid):
        conf = "medium"
        checks.append({"pass": 2, "level": "note",
                       "reason": "Onkelos recasts this pasuk; Magil gives the literal pshat — compare",
                       "proposed_fix": ""})
    else:
        conf = "high"
        if pw["supplied"]:
            checks.append({"pass": 1, "level": "note",
                           "reason": "Magil supplies bracketed word(s) for readability (standard linear practice)",
                           "proposed_fix": ""})
    dist[conf] += 1
    selfcheck[str(wid)] = {"confidence": conf, "check_results": checks}
Wj(os.path.join(STG, "selfcheck_magil.json"), selfcheck)

print("=" * 60)
print("PHASE 1 — SPAN ASSIGNMENT (span-centric)")
print("=" * 60)
print(f"Pesukim: {len(by_cv)}   fully 1:1-forced: {confident_pesukim}")
print(f"Grouped spans (faithful, split-pending): {grouped_spans}  covering {words_in_group} words")
print(f"\nFINAL SPLIT:")
for k in ("high", "medium", "low"):
    print(f"  {k:7} {dist[k]:5}")
print(f"  total   {sum(dist.values()):5}")
print(f"\nEvery word shows Magil's real English (0 on dictionary junk).")
print(f"HIGH = per-word 1:1. MEDIUM = correct phrase, grouping/recast/particle pending.")
