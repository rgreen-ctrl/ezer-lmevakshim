"""Merge Pass 3 (AI, flags-only) findings into passes 1&2, compute a per-word
confidence (high|medium|low) that ONLY orders review, and write the final map.

Pass 3 findings from the AI reviewer are recurring wrong-sense glosses; they are
propagated deterministically to every word carrying that gloss. Confidence never
approves anything.
"""
import json
import re
import unicodedata
from pathlib import Path

STAGE = Path("data/staging")
HEB = re.compile(r"[א-ת]")

# Pass 3 (AI reviewer) — recurring wrong-sense glosses -> concern.
PASS3 = {
    "hypocrite": "wrong sense: אדם = man/mankind here (gloss shows 'hypocrite')",
    "band, bank": "wrong sense: שפה = language/lip (or edge) here",
    "care for, comfortably": "wrong sense: לב = heart here",
    "carpenter, gallows": "wrong sense: עץ = wood/timber here",
    "burn incense": "wrong sense: זכר = remembered here",
    "alienate, alter": "wrong sense: עבר = caused to pass over here",
    "make an atonement": "wrong sense: כפר = cover/coat (with pitch) here",
    "bribe, camphire": "wrong sense: כפר = pitch/bitumen here",
    "abate, make bright": "check sense: קלל = curse (לקלל) vs be-light",
}


def cons(s):
    return "".join(ch for ch in unicodedata.normalize("NFD", s or "") if HEB.match(ch))


def main():
    pre = json.loads((STAGE / "selfcheck_pre.json").read_text("utf-8"))
    out, dist = {}, {"high": 0, "medium": 0, "low": 0}
    for wid, r in pre.items():
        reasons = list(r["reasons"])
        gloss = r["gloss"] or ""
        for pat, concern in PASS3.items():
            if pat in gloss:
                reasons.append({"pass": 3, "level": "concern",
                                "reason": concern, "proposed_fix": ""})
                break
        if r["flagged"]:
            reasons.append({"pass": 0, "level": "flag",
                            "reason": "prior flag (verb / particle / empty gloss)",
                            "proposed_fix": ""})
        hard = any(x["pass"] in (1, 2, 3) or x["level"] == "flag" for x in reasons)
        if hard:
            conf = "low"
        elif r["recast"]:
            reasons.append({"pass": 2, "level": "note",
                            "reason": "Onkelos recasts this pasuk (labeled, not literal)",
                            "proposed_fix": ""})
            conf = "medium"
        else:
            conf = "high"
        dist[conf] += 1
        out[wid] = {"confidence": conf, "check_results": reasons}
    (Path("data/selfcheck_noach.json")).write_text(
        json.dumps(out, ensure_ascii=False), "utf-8")
    print("DISTRIBUTION:", json.dumps(dist),
          f"| total={sum(dist.values())}")
    print("\n--- 6:9-6:11 LOW pile (word -> confidence + reasons) ---")
    for wid, r in pre.items():
        if r["ref"] in ("Bereishis 6:9", "Bereishis 6:10", "Bereishis 6:11"):
            fr = out[wid]
            if fr["confidence"] == "low":
                rs = "; ".join(x["reason"] for x in fr["check_results"])
                print(f'{r["ref"]} {r["he"]} [{fr["confidence"].upper()}] {rs}')


if __name__ == "__main__":
    main()
