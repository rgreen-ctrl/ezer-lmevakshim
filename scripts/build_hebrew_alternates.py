#!/usr/bin/env python3
"""Hebrew-grounded alternate renderings — from the WORD, not Magil's English.

For each verb: shoresh's clean sense (root_gloss) + morphhb tags (binyan,
person/gender/number, vav prefix) -> 2-3 candidate renderings composed
MECHANICALLY from what the grammar supports. Nothing interprets; nothing
borrows another root's meaning; where tags don't parse confidently, nothing
is proposed. Chips labeled by what grounds them ("Hebrew: hifil, he + root").
Magil's chip stays alongside — he is still the base.

Also reports: words with alternates, distinct shoresh+binyan combos (the
genealogy insight: decide hifil-ילד once, chapters 10-11 follow).
"""
import json, re, sys
from pathlib import Path
from collections import Counter, defaultdict
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from build_contextual import parse_morphhb, ref_to_cv

def L(p): return json.loads(p.read_text(encoding="utf-8-sig"))
lw = L(ROOT/"data"/"staging"/"live_words.json")
roots = L(ROOT/"data"/"root_gloss_noach.json")
sugg_p = ROOT/"data"/"suggestions_noach.json"; sugg = L(sugg_p)
morph = parse_morphhb()

PRON = {"1cs":"I","2ms":"you","2fs":"you","3ms":"he","3fs":"she",
        "1cp":"we","2mp":"you","3mp":"they","3fp":"they","3cp":"they"}
# INFLECT OR PROPOSE NOTHING (Rabbi Green's ruling): a template may only be
# emitted when the root's needed English forms are in this curated table.
# {root_gloss: (past, participle)} — extend as combos get decided.
INFLECT = {
    "bore (child)": ("fathered", "born"), "was": ("was", "been"),
    "lived": ("lived", "lived"), "made/did": ("made", "made"),
    "said": ("said", "said"), "came/brought": ("came", "brought"),
    "took": ("took", "taken"), "went out": ("went out", "gone out"),
    "fill": ("filled", "filled"), "corrupted": ("corrupted", "corrupted"),
    "saw": ("saw", "seen"), "walked": ("walked", "walked"),
    "died": ("died", "died"), "went": ("went", "gone"),
    "blessed": ("blessed", "blessed"), "built": ("built", "built"),
    "sent": ("sent", "sent"), "returned": ("returned", "returned"),
}
# binyan -> templates over (pron, root). Mechanical composition only.
TPL = {
    "q": ["{p} {r}"],
    "N": ["{p} was {r}", "there was {r} to {p2}"],
    "p": ["{p} {r} (intensive)"],
    "P": ["{p} was {r} (intensive)"],
    "h": ["{p} caused to be {r}", "there were {r} to {p2}", "{p} had {r}"],
    "H": ["{p} was caused to {r}"],
    "t": ["{p} {r} (oneself)"],
}
OBJ = {"he":"him","she":"her","they":"them","you":"you","I":"me","we":"us"}
LABEL_PRE = "Hebrew: "

byref = defaultdict(list)
for w in lw: byref[w["ref"]].append(w)
for ws in byref.values(): ws.sort(key=lambda w: w["pos"])

# idempotent
for wid in sugg:
    sugg[wid] = [c for c in sugg[wid]
                 if not c.get("source_label","").startswith(LABEL_PRE)]

combos = Counter(); covered = 0
for ref, ws in byref.items():
    mws = morph.get(ref_to_cv(ref), [])
    if len(mws) != len(ws): continue
    for w, mw in zip(ws, mws):
        cm = mw.get("content_morph") or ""
        if not cm.startswith("V") or len(cm) < 3: continue
        root = (roots.get(str(w["id"])) or {}).get("root_gloss")
        if not root: continue
        m = re.search(r"([123][a-z][a-z])$", cm)
        pron = PRON.get(m.group(1)) if m else None
        if not pron: continue                    # tags don't support -> nothing
        biny = cm[1]
        tpls = TPL.get(biny)
        if not tpls: continue
        forms = INFLECT.get(root)
        if not forms:
            continue                     # no known inflection -> SILENCE
        past, part = forms
        vav = "and " if "and" in (mw.get("prefixes") or []) else ""
        combos[(root, biny)] += 1
        chips = sugg.setdefault(str(w["id"]), [])
        names = {"q":"kal","N":"nifal","p":"piel","P":"pual","h":"hifil","H":"hofal","t":"hitpael"}
        for t in tpls:
            # past form in active frames, participle in passive/there-were frames
            r = part if ("was" in t or "were" in t or "caused" in t) else past
            txt = vav + t.format(p=pron, r=r, p2=OBJ.get(pron, pron))
            chips.append({"source_label": f"{LABEL_PRE}{names[biny]}, {m.group(1)}",
                          "text": txt, "recast": False})
        covered += 1

sugg_p.write_text(json.dumps(sugg, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"verbs given Hebrew-grounded alternates: {covered}")
print(f"distinct shoresh+binyan combos: {len(combos)}")
print("top combos (decide once, the rest follow):")
for (r, b), n in combos.most_common(8):
    print(f"  {r} [{b}]: {n} words")
