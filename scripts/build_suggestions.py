"""Build grounded, source-LABELED contextual suggestion sets per Noach word.

Options (only those with genuine content, in this order):
  Morphology (morphhb)  - the affix-folded composed draft   [default]
  Binyan: <name>        - non-qal verb form nuance (morphhb tag + root gloss)
  Onkelos (Etheridge)   - PD English, per pasuk; recast-flagged
  Rashi                 - PD Rosenbaum-Silbermann CAPS gloss, lemma-matched
  Root gloss            - the plain live root gloss
Magil is omitted (OCR too noisy to trust per word). Nothing invented; empty
sources are omitted. Output: suggestions_map.json {word_id: [ {text,
source_label, recast} ]}. Reports coverage over the 578 flagged words.
"""
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

STAGE = Path("data/staging")
OSIS = "{http://www.bibletechnologies.net/2003/OSIS/namespace}"
HEB = re.compile(r"[א-ת]")

BINYAN = {
    "N": ("Nifal", lambda g: f"was {g} / {g} itself"),
    "p": ("Piel", lambda g: f"{g} (intensive)"),
    "P": ("Pual", lambda g: f"was {g} (intensive passive)"),
    "h": ("Hifil", lambda g: f"caused to {g}"),
    "H": ("Hofal", lambda g: f"was caused to {g}"),
    "t": ("Hitpael", lambda g: f"{g} about / conducted (oneself)"),
}
RECAST_MARKERS = ["fear of the Lord", "Word of the Lord", "Memra",
                  "glory of the Lord", "before the Lord", "the Lord"]


def cons(s):
    return "".join(ch for ch in unicodedata.normalize("NFD", s or "") if HEB.match(ch))


def parse_morphhb():
    tree = ET.parse(STAGE / "morphhb_Gen.xml")
    verses = {}
    for verse in tree.iter(f"{OSIS}verse"):
        _, c, v = verse.get("osisID").split(".")
        c, v = int(c), int(v)
        if (c, v) < (6, 9) or (c, v) > (11, 32):
            continue
        ws = []
        for w in verse.findall(f"{OSIS}w"):
            morph = w.get("morph", "")
            morph = morph[1:] if morph[:1] in ("H", "A") else morph
            content = next((m for m in morph.split("/")
                            if not m.startswith(("R", "C", "T", "S"))), "")
            ws.append({"he": (w.text or "").replace("/", ""),
                       "content": content})
        verses[(c, v)] = ws
    return verses


def rashi_caps(comment):
    """Extract the CAPS translation R-S puts right after the Hebrew lemma,
    plus the leading Hebrew lemma tokens (for word matching). Returns
    (lemma_tokens, caps_text) or (None, None)."""
    head = re.split(r"\s[—-]\s", comment, maxsplit=1)[0]  # before em/en dash
    heb_tokens = [cons(t) for t in head.split() if HEB.search(t)]
    caps = " ".join(t for t in head.split() if not HEB.search(t))
    caps = caps.strip(" .,;:")
    if not heb_tokens or not caps or len(caps.split()) > 6:
        return None, None
    return set(heb_tokens), caps.lower()


def main():
    live = json.loads((STAGE / "live_words.json").read_text("utf-8-sig"))
    ctx = json.loads((Path("data/contextual_noach.json")).read_text("utf-8"))
    onk = json.loads((STAGE / "onkelos_ether.json").read_text("utf-8-sig"))
    rashi = json.loads((STAGE / "rashi_rs.json").read_text("utf-8-sig"))
    morph = parse_morphhb()

    byverse = {}
    for w in live:
        m = re.search(r"(\d+):(\d+)", w["ref"])
        byverse.setdefault((int(m.group(1)), int(m.group(2))), []).append(w)
    for lst in byverse.values():
        lst.sort(key=lambda w: w["pos"])

    out, stats = {}, {"flagged": 0, "flagged_ge2": 0, "flagged_only_root": 0,
                      "onkelos_words": 0, "rashi_words": 0, "binyan_words": 0}
    for (c, v), lwords in sorted(byverse.items()):
        mwords = morph.get((c, v), [])
        aligned = len(mwords) == len(lwords) and all(
            cons(a["he"]) == cons(b["he"]) for a, b in zip(mwords, lwords))
        onk_txt = (onk.get(str(c)) or [None] * v)[v - 1] if str(c) in onk else None
        rashi_comments = (rashi.get(str(c)) or [])
        rc = rashi_comments[v - 1] if str(c) in rashi and v - 1 < len(rashi_comments) else []
        parsed_rashi = [rashi_caps(cm) for cm in (rc or [])]
        for i, lw in enumerate(lwords):
            rec = ctx.get(str(lw["id"]), {})
            gloss = (lw["tr"] or "").strip()
            contextual = (rec.get("contextual") or "").strip()
            flagged = bool(rec.get("flagged"))
            opts = []
            if contextual:
                opts.append({"text": contextual,
                             "source_label": "Morphology (morphhb)", "recast": False})
            # binyan
            mw = mwords[i] if aligned and i < len(mwords) else None
            if mw and mw["content"].startswith("V") and len(mw["content"]) > 1:
                nm = BINYAN.get(mw["content"][1])
                if nm and gloss:
                    opts.append({"text": nm[1](gloss),
                                 "source_label": f"Binyan: {nm[0]}", "recast": False})
                    stats["binyan_words"] += 1
            # onkelos (per pasuk)
            if onk_txt:
                clean = re.sub("<[^>]+>", "", onk_txt).strip()
                is_recast = any(mk in clean for mk in RECAST_MARKERS)
                opts.append({"text": clean, "source_label": "Onkelos (Etheridge, per pasuk)",
                             "recast": is_recast})
                stats["onkelos_words"] += 1
            # rashi (lemma matched) - but never bind a phrase comment to a
            # proper name (e.g. "NOAH WALKED WITH GOD" must not attach to נח)
            wc = cons(lw["he"])
            is_np = bool(mw and mw["content"].startswith("Np"))
            for toks, caps in ([] if is_np else parsed_rashi):
                if toks and wc in toks:
                    opts.append({"text": caps, "source_label": "Rashi", "recast": False})
                    stats["rashi_words"] += 1
                    break
            # root gloss
            if gloss:
                opts.append({"text": gloss, "source_label": "Root gloss", "recast": False})
            out[str(lw["id"])] = opts
            if flagged:
                stats["flagged"] += 1
                distinct = {o["text"] for o in opts}
                if len(distinct) >= 2:
                    stats["flagged_ge2"] += 1
                elif distinct <= {gloss}:
                    stats["flagged_only_root"] += 1
    (STAGE / "suggestions_map.json").write_text(
        json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print("STATS:", json.dumps(stats))
    print("\n--- 6:9 sample (bedorotav + hithalech) ---")
    for w in byverse[(6, 9)]:
        if cons(w["he"]) in (cons("בדרתיו"), cons("התהלך")):
            print(f'\n{w["he"]}:')
            for o in out[str(w["id"])]:
                r = " [RECAST]" if o["recast"] else ""
                print(f'   ({o["source_label"]}) "{o["text"]}"{r}')


if __name__ == "__main__":
    main()
