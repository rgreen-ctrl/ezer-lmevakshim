#!/usr/bin/env python3
"""Phase 5 — readability (Pass 4). Propose PLAINER English for Magil's archaic
1905 wording, as a labeled 'Plainer English' suggestion chip. HARD LIMIT: same
meaning, plainer words only. Swaps come from a curated, meaning-preserving map
(thou->you, unto->to, shalt->shall, begat->fathered, …). Words carrying an
archaic term whose plainer form could shift sense (behold, abroad, …) are
FLAGGED with NO proposal — accuracy outranks readability, so when in doubt we
propose nothing. Nothing here changes a gloss or certifies; the chip is an
optional fill, exactly like the other suggestion chips.

Mutates (idempotently) data/suggestions_noach.json and data/selfcheck_noach.json.
"""
import json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
def L(p): return json.load(open(p, encoding="utf-8-sig"))
def Wj(p, o): json.dump(o, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# Meaning-preserving archaic -> plain. Each is a straight modernization that a
# reader would accept as the same word, not a reinterpretation.
SAFE = {
    "unto": "to", "thou": "you", "thee": "you", "thy": "your", "thine": "your",
    "ye": "you", "shalt": "shall", "hast": "have", "hath": "has", "doth": "does",
    "dost": "do", "art": "are", "wast": "were", "wilt": "will", "canst": "can",
    "goest": "go", "doest": "do", "thence": "from there", "whence": "from where",
    "begat": "fathered",
}
# Archaic but meaning-sensitive — flag for his eye, propose nothing.
FLAG_ONLY = {"behold", "abroad", "yea", "wherefore", "hearken", "smote", "spake"}

def preserve_case(src, repl):
    return repl[:1].upper() + repl[1:] if src[:1].isupper() else repl

def plainer(text):
    """Return (plainer_text, changed_bool)."""
    def sub(m):
        w = m.group(0)
        return preserve_case(w, SAFE[w.lower()])
    pattern = re.compile(r"\b(" + "|".join(sorted(SAFE, key=len, reverse=True)) + r")\b", re.I)
    out = pattern.sub(sub, text)
    return out, (out != text)

def flags_in(text):
    low = set(re.findall(r"[a-z]+", text.lower()))
    return sorted(FLAG_ONLY & low)

sugg = L(os.path.join(DATA, "suggestions_noach.json"))
selfcheck = L(os.path.join(DATA, "selfcheck_noach.json"))
ctx = L(os.path.join(DATA, "contextual_noach.json"))

proposed = flagged = 0
for wid, rec in ctx.items():
    text = rec.get("contextual") or ""
    if not text:
        continue
    chips = sugg.get(wid, [])
    chips = [c for c in chips if c.get("source_label") != "Plainer English"]  # idempotent
    plain, changed = plainer(text)
    if changed:
        # insert right after the Magil base chip (keep the accurate source first)
        insert_at = 1 if chips and chips[0].get("base") else 0
        chips.insert(insert_at, {"source_label": "Plainer English", "text": plain,
                                 "recast": False, "readability": True})
        proposed += 1
    sugg[wid] = chips

    fl = flags_in(text)
    if fl:
        sc = selfcheck.get(wid)
        if sc is not None:
            sc["check_results"] = [r for r in sc["check_results"]
                                   if r.get("pass") != 4]     # idempotent
            sc["check_results"].append({
                "pass": 4, "level": "note",
                "reason": f"archaic wording ({', '.join(fl)}) — a plainer word is your call; "
                          f"meaning unchanged, so nothing is proposed automatically",
                "proposed_fix": ""})
            flagged += 1

Wj(os.path.join(DATA, "suggestions_noach.json"), sugg)
Wj(os.path.join(DATA, "selfcheck_noach.json"), selfcheck)
print("READABILITY PASS (Pass 4)")
print(f"  Plainer English chips proposed : {proposed}")
print(f"  words flagged (archaic, no auto-proposal): {flagged}")
print(f"  safe swaps used: {', '.join(sorted(SAFE))}")
print(f"  flag-only (never auto-swapped): {', '.join(sorted(FLAG_ONLY))}")
