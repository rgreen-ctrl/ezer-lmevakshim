"""Compose DRAFT contextual translations for Noach, grounded in morphhb
morphology (CC-BY) + the live root glosses. Flags every judgment case.

Inputs (staging): morphhb_Gen.xml, live_words.json
Output: contextual_map.json  -> {word_id: {contextual, flagged, note}}
Prints stats + the first three pesukim for eyeball review.
NO certification, NO invention: content root meaning always comes from the
live gloss; only prefixes/suffixes/order are added deterministically.
"""
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

STAGE = Path("data/staging")
OSIS = "{http://www.bibletechnologies.net/2003/OSIS/namespace}"

PREFIX = {"b": "in", "c": "and", "d": "the", "h": "the",
          "k": "like", "l": "to", "m": "from", "s": "that"}
SUFFIX = {"1cs": "my", "2ms": "your", "2fs": "your", "3ms": "his",
          "3fs": "her", "1cp": "our", "2mp": "your", "2fp": "your",
          "3mp": "their", "3fp": "their"}

HEB_LETTERS = re.compile(r"[א-ת]")


def consonants(s):
    s = unicodedata.normalize("NFD", s or "")
    return "".join(ch for ch in s if HEB_LETTERS.match(ch))


def parse_morphhb():
    """Return {(chap,verse): [ {he, prefixes:[str], suffix:str|None,
    content_morph:str, is_verb, is_np, is_particle} ] } for Gen 6:9-11:32."""
    tree = ET.parse(STAGE / "morphhb_Gen.xml")
    verses = {}
    for verse in tree.iter(f"{OSIS}verse"):
        osis = verse.get("osisID")  # Gen.C.V
        _, c, v = osis.split(".")
        c, v = int(c), int(v)
        if (c, v) < (6, 9) or (c, v) > (11, 32):
            continue
        words = []
        for w in verse.findall(f"{OSIS}w"):
            text = w.text or ""
            lemma = w.get("lemma", "")
            morph = w.get("morph", "")
            morph = morph[1:] if morph[:1] in ("H", "A") else morph  # drop lang
            mseg = morph.split("/")
            lseg = lemma.split("/")
            prefixes, suffix = [], None
            content_morph = ""
            for i, m in enumerate(mseg):
                lem = lseg[i] if i < len(lseg) else ""
                if m.startswith("R") and i < len(mseg) - 1 and lem in PREFIX:
                    prefixes.append(PREFIX[lem])
                elif m.startswith("C"):
                    prefixes.append("and")
                elif m.startswith("Td"):
                    prefixes.append("the")
                elif m.startswith("Tr"):
                    prefixes.append("that")
                elif m.startswith("Sp"):
                    suffix = SUFFIX.get(m[2:5], None)
                elif not content_morph:
                    content_morph = m
            words.append({
                "he": text.replace("/", ""),
                "prefixes": prefixes,
                "suffix": suffix,
                "content_morph": content_morph,
                "is_verb": content_morph.startswith("V"),
                "is_np": content_morph.startswith("Np"),
                # a lone preposition/particle as the content (e.g. את = R)
                "is_particle": content_morph.startswith(("R", "T"))
                and not prefixes,
            })
        verses[(c, v)] = words
    return verses


def ref_to_cv(ref):  # "Bereishis 6:9" -> (6, 9)
    m = re.search(r"(\d+):(\d+)", ref)
    return (int(m.group(1)), int(m.group(2)))


def compose(prefixes, suffix, root_gloss, is_verb, is_np):
    parts = list(prefixes)
    if suffix and not is_verb:      # possessive on a noun
        parts.append(suffix)
    parts.append(root_gloss)
    return " ".join(p for p in parts if p).strip()


def main():
    live = json.loads((STAGE / "live_words.json").read_text(encoding="utf-8-sig"))
    morph = parse_morphhb()

    # group live words by verse, in order
    byverse = {}
    for w in live:
        byverse.setdefault(ref_to_cv(w["ref"]), []).append(w)
    for v in byverse.values():
        v.sort(key=lambda w: w["pos"])

    out = {}
    stats = {"total": 0, "composed": 0, "flagged": 0, "mismatch_verses": 0,
             "empty_gloss": 0, "verbs": 0, "particles": 0, "propernouns": 0}
    for cv, lwords in sorted(byverse.items()):
        mwords = morph.get(cv, [])
        aligned = len(mwords) == len(lwords) and all(
            consonants(a["he"]) == consonants(b["he"])
            for a, b in zip(mwords, lwords))
        if not aligned:
            stats["mismatch_verses"] += 1
        for i, lw in enumerate(lwords):
            stats["total"] += 1
            flags, note = False, []
            gloss = (lw["tr"] or "").strip()
            mw = mwords[i] if aligned and i < len(mwords) else None
            if mw is None:
                # can't trust morphology here -> flag, fall back to gloss
                flags = True
                note.append("alignment mismatch - verify affixes")
                contextual = gloss
            else:
                if not gloss:
                    flags = True; note.append("empty gloss - needs translation")
                    stats["empty_gloss"] += 1
                if mw["is_verb"]:
                    flags = True; note.append("verb - check tense/person")
                    stats["verbs"] += 1
                if mw["is_np"]:
                    note.append("proper name (transliteration)")
                    stats["propernouns"] += 1
                if mw["is_particle"]:
                    flags = True; note.append("particle (e.g. es) - object-marker vs 'with'")
                    stats["particles"] += 1
                if mw["suffix"] and mw["is_verb"]:
                    flags = True; note.append("object-pronoun suffix - check")
                if len(mw["prefixes"]) > 1:
                    note.append("multiple prefixes - check order")
                contextual = compose(mw["prefixes"], mw["suffix"], gloss,
                                     mw["is_verb"], mw["is_np"])
            if flags:
                stats["flagged"] += 1
            if contextual:
                stats["composed"] += 1
            out[str(lw["id"])] = {
                "contextual": contextual,
                "flagged": flags,
                "note": "; ".join(note)[:255],
                "ref": lw["ref"], "pos": lw["pos"], "he": lw["he"], "gloss": gloss,
            }
    (STAGE / "contextual_map.json").write_text(
        json.dumps(out, ensure_ascii=False), encoding="utf-8")

    print("STATS:", json.dumps(stats))
    print("\n--- 6:9 to 6:11 (review) ---")
    for wid, r in out.items():
        if r["ref"] in ("Bereishis 6:9", "Bereishis 6:10", "Bereishis 6:11"):
            flag = "  [FLAG: %s]" % r["note"] if r["flagged"] else ""
            print(f'{r["ref"]} p{r["pos"]:>2} {r["he"]}  ->  "{r["contextual"]}"{flag}')


if __name__ == "__main__":
    main()
