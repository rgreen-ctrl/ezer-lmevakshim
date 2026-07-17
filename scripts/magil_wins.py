#!/usr/bin/env python3
"""Magil wins on conflict + name map. DATA BUILD (report; seeder applies to DB).

L1 (shoresh): from the per-word Magil chip, strip supplied []/() text, ellipses,
footnote marks and function words; if exactly ONE content word remains, that is
Magil's unambiguous word for this root -> prefill root_gloss (kets: 'The end
of' -> 'end'). More than one content word left = a guess -> silence.
L2 (literal): Magil (split) + Magil (ellipsis collapsed) chips -> prefill
translation. Brackets/parens never map.
NAME MAP (approved): people + all places; Nineveh unchanged; possessives;
divine names excluded; applied to Magil English (lines/contextual/chips) and
Strong's name entries. R-S untouched. Certified: seeder flags, never writes.
"""
import json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
def L(p): return json.loads(p.read_text(encoding="utf-8-sig"))
def W(p, o): p.write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")

sugg_p = ROOT/"data"/"suggestions_noach.json"; sugg = L(sugg_p)
ctx_p = ROOT/"data"/"contextual_noach.json"; ctx = L(ctx_p)
lines_p = ROOT/"app"/"static"/"magil_lines.json"; lines = L(lines_p)

# ---- name map (approved list; identical-pairs omitted) ----
NM = {"Noah":"Noach","Japheth":"Yefes","Ham":"Cham","Nahor":"Nachor","Abram":"Avram",
"Canaan":"Kenaan","Milcah":"Milkah","Iscah":"Yiskah","Eber":"Ever","Calah":"Kalach",
"Shelah":"Shelach","Terah":"Terach","Assyria":"Ashur","Asshur":"Ashur",
"Rehoboth-Ir":"Rechovos-Ir","Cush":"Kush","Joktan":"Yoktan","Javan":"Yavan",
"Havilah":"Chavilah","Sheba":"Sheva","Babel":"Bavel","Zidon":"Tzidon",
"Mizraim":"Mitzrayim","Canaanite":"Kenaani","Chaldees":"Kasdim","Tubal":"Tuval",
"Riphath":"Rifas","Seba":"Seva","Accad":"Akkad","Calneh":"Kalneh","Lehabim":"Lehavim",
"Pathrusim":"Pasrusim","Casluhim":"Kasluchim","Heth":"Cheis","Jebusite":"Yevusi",
"Amorite":"Emori","Girgashite":"Girgashi","Hivite":"Chivi","Arkite":"Arki",
"Sinite":"Sini","Arvadite":"Arvadi","Zemarite":"Tzemari","Hamathite":"Chamasi",
"Obal":"Oval","Abimael":"Avimael","Ophir":"Ofir","Jobab":"Yovav","Sephar":"Sefar",
"Sabtah":"Savtah","Sabteca":"Savtecha","Naphtuhim":"Naftuchim","Philistines":"Pelishtim",
"Caphtorim":"Kaftorim","Gaza":"Azah","Zeboiim":"Tzevoyim","Sodom":"Sedom",
"Gomorrah":"Amorah","Lasha":"Lesha","Elam":"Eilam","Uz":"Utz","Hul":"Chul",
"Gether":"Geser","Sheleph":"Shelef","Hazarmaveth":"Chatzarmaves","Jerah":"Yerach",
"Haron":"Haran"}
PAT = re.compile(r"\b(" + "|".join(sorted(NM, key=len, reverse=True)) + r")('s)?\b")
def rename(t):
    return PAT.sub(lambda m: NM[m.group(1)] + (m.group(2) or ""), t or "")

renamed = 0
def rn(t):
    global renamed
    n = rename(t)
    if n != t: renamed += 1
    return n

for ref, e in lines.items():
    for ln in e["lines"]:
        ln["en"] = rn(ln["en"])
W(lines_p, lines)

MAGIL_LABELS = ("Magil (linear, 1905)","Magil literal (Heb.)","Magil (split)",
                "Magil (ellipsis collapsed)","Plainer English","Shoresh (root)")
for wid, chips in sugg.items():
    for c in chips:
        if c.get("source_label","").startswith(MAGIL_LABELS):
            c["text"] = rn(c["text"])
for wid, r in ctx.items():
    if r.get("contextual"): r["contextual"] = rn(r["contextual"])
W(ctx_p, ctx)

# ---- Magil-wins prefill data ----
SUP = re.compile(r"\[[^\]]*\]|\([^)]*\)|…|\.\.\.|[¹²³⁴⁵⁶⁷⁸⁹]")
FUNC = {"the","a","an","of","and","in","to","with","for","from","on","at","by",
        "was","were","is","are","be","he","she","it","they","thou","thee","thy"}
prefill = {}   # wid -> {l1, l2}
for wid, chips in sugg.items():
    by = {c["source_label"]: c["text"] for c in chips}
    l2 = by.get("Magil (split)") or by.get("Magil (ellipsis collapsed)")
    l1 = None
    base = by.get("Magil (linear, 1905)")
    if base:
        toks = [t for t in re.findall(r"[A-Za-z][A-Za-z'\-]*", SUP.sub(" ", base))
                if t.lower() not in FUNC]
        if len(toks) == 1:
            l1 = toks[0].lower() if not toks[0][0].isupper() else toks[0]
    if l1 or l2:
        prefill[wid] = {"l1": l1, "l2": l2}
W(ROOT/"data"/"magil_prefill.json", prefill)
n1 = sum(1 for v in prefill.values() if v["l1"])
n2 = sum(1 for v in prefill.values() if v["l2"])
print(f"name-map substitutions applied in data: {renamed}")
print(f"L1 prefill candidates (single content word): {n1}")
print(f"L2 prefill candidates (split+collapse): {n2}")
print(f"fallback to composer/Strong's: L1 {1861-n1}, L2 {1861-n2}")
