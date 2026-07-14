"""Passes 1 & 2 of the self-check (deterministic), plus per-pasuk assembly
for the Pass-3 AI read. Never rewrites/approves; only produces flags + a
proposed fix. Outputs:
  selfcheck_pre.json      {word_id: {reasons:[{pass,level,reason,proposed_fix}],
                                     flagged, gloss, draft}}
  pesukim_assembled.json  {"C:V": "word1 / word2 / ..."}  (for Pass 3)
"""
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

STAGE = Path("data/staging")
OSIS = "{http://www.bibletechnologies.net/2003/OSIS/namespace}"
HEB = re.compile(r"[א-ת]")
STOP = {"in", "his", "her", "their", "the", "a", "of", "and", "with", "to",
        "is", "was", "for", "on", "he", "she", "it", "its", "my", "your", "our"}


def cons(s):
    return "".join(ch for ch in unicodedata.normalize("NFD", s or "") if HEB.match(ch))


def content_morph(w):
    morph = w.get("morph", "")
    morph = morph[1:] if morph[:1] in ("H", "A") else morph
    return next((m for m in morph.split("/")
                 if not m.startswith(("R", "C", "T", "S"))), "")


def parse_morphhb():
    tree = ET.parse(STAGE / "morphhb_Gen.xml")
    verses = {}
    for verse in tree.iter(f"{OSIS}verse"):
        _, c, v = verse.get("osisID").split(".")
        c, v = int(c), int(v)
        if (c, v) < (6, 9) or (c, v) > (11, 32):
            continue
        verses[(c, v)] = [{"he": (w.text or "").replace("/", ""),
                           "cm": content_morph(w)} for w in verse.findall(f"{OSIS}w")]
    return verses


def pluralize(word):
    if word.endswith(("s", "x", "z", "ch", "sh")):
        return word + "es"
    if word.endswith("y") and word[-2:-1] not in "aeiou":
        return word[:-1] + "ies"
    return word + "s"


def content_tokens(text):
    return {t for t in re.findall(r"[a-z]+", (text or "").lower()) if t not in STOP}


def main():
    live = json.loads((STAGE / "live_words.json").read_text("utf-8-sig"))
    ctx = json.loads(Path("data/contextual_noach.json").read_text("utf-8"))
    sugg = json.loads((STAGE / "suggestions_map.json").read_text("utf-8"))
    morph = parse_morphhb()

    byverse = {}
    for w in live:
        m = re.search(r"(\d+):(\d+)", w["ref"])
        byverse.setdefault((int(m.group(1)), int(m.group(2))), []).append(w)
    for lst in byverse.values():
        lst.sort(key=lambda w: w["pos"])

    pre, assembled = {}, {}
    for (c, v), lwords in sorted(byverse.items()):
        mwords = morph.get((c, v), [])
        aligned = len(mwords) == len(lwords) and all(
            cons(a["he"]) == cons(b["he"]) for a, b in zip(mwords, lwords))
        drafts_for_pasuk = []
        for i, lw in enumerate(lwords):
            rec = ctx.get(str(lw["id"]), {})
            gloss = (lw["tr"] or "").strip()
            draft = (rec.get("contextual") or "").strip()
            flagged = bool(rec.get("flagged"))
            options = sugg.get(str(lw["id"]), [])
            reasons = []
            mw = mwords[i] if aligned and i < len(mwords) else None

            # --- PASS 1: morphology consistency (deterministic) -------------
            if mw and mw["cm"].startswith("N") and len(mw["cm"]) >= 4:
                number = mw["cm"][3]  # s / p / d
                simple = gloss and " " not in gloss and gloss.isalpha()
                if number in ("p", "d") and simple and not gloss.endswith("s"):
                    fixed = pluralize(gloss)
                    proposed = (draft.rsplit(gloss, 1)[0] + fixed) if gloss in draft else fixed
                    reasons.append({"pass": 1, "level": "mismatch",
                                    "reason": f"number: morphhb marks plural, draft '{draft}' looks singular",
                                    "proposed_fix": proposed})

            # --- PASS 2: cross-source agreement -----------------------------
            binyan = next((o for o in options if o["source_label"].startswith("Binyan")), None)
            if binyan and draft and binyan["text"] != draft and gloss and draft.strip() == gloss:
                reasons.append({"pass": 2, "level": "disagree",
                                "reason": f"binyan sense differs: draft '{draft}' vs {binyan['source_label']} '{binyan['text']}'",
                                "proposed_fix": binyan["text"]})
            rashi = next((o for o in options if o["source_label"] == "Rashi"), None)
            if rashi and draft:
                dt, rt = content_tokens(draft), content_tokens(rashi["text"])
                if dt and rt and not (dt & rt):
                    reasons.append({"pass": 2, "level": "disagree",
                                    "reason": f"Rashi differs: '{rashi['text']}' vs draft '{draft}'",
                                    "proposed_fix": rashi["text"]})
            onk = next((o for o in options if o["source_label"].startswith("Onkelos")), None)
            recast = bool(onk and onk.get("recast"))

            pre[str(lw["id"])] = {"reasons": reasons, "flagged": flagged,
                                  "recast": recast, "gloss": gloss, "draft": draft,
                                  "ref": lw["ref"], "he": lw["he"]}
            drafts_for_pasuk.append(draft or gloss or "?")
        assembled[f"{c}:{v}"] = " / ".join(drafts_for_pasuk)

    (STAGE / "selfcheck_pre.json").write_text(json.dumps(pre, ensure_ascii=False), "utf-8")
    (STAGE / "pesukim_assembled.json").write_text(json.dumps(assembled, ensure_ascii=False), "utf-8")

    p1 = sum(1 for r in pre.values() if any(x["pass"] == 1 for x in r["reasons"]))
    p2 = sum(1 for r in pre.values() if any(x["pass"] == 2 for x in r["reasons"]))
    print(f"Pass1 mismatches: {p1} | Pass2 disagreements: {p2} | pesukim: {len(assembled)}")
    print("6:9 bedorotav pass1:", [r for r in pre.values()
          if r["ref"] == "Bereishis 6:9" and cons(r["he"]) == cons("בדרתיו")][0]["reasons"])


if __name__ == "__main__":
    main()
