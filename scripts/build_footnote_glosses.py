#!/usr/bin/env python3
"""Feed Magil's 'Heb.' footnotes into the LITERAL layer (Layer 2) as chips.

A 'Heb.' note gives the literal Hebrew behind Magil's readable English — e.g.
his line "⁴rooms" carries "Heb. nests", so קִנִּים is literally "nests". That is
exactly Layer 2's job.

Only attached where the note's line covers ONE Hebrew word: then the note
belongs to that word unambiguously. Where the line covers several words, which
word the note refers to is a guess, so it is left as a readable page-bottom
note only. 'Or./As.' notes are variant readings, never a literal — skipped.

Adds a "Magil literal (Heb.)" chip (the Desk routes it to the literal field).
Idempotent.
"""
import json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def L(p): return json.load(open(p, encoding="utf-8-sig"))

lines = L(os.path.join(ROOT, "app", "static", "magil_lines.json"))
lw = L(os.path.join(ROOT, "data", "staging", "live_words.json"))
sugg_path = os.path.join(ROOT, "data", "suggestions_noach.json")
sugg = L(sugg_path)

LABEL = "Magil literal (Heb.)"
pos2id = {(w["ref"], w["pos"]): w["id"] for w in lw}
strip = lambda t: re.sub(r"^\s*(Heb|H)\.\s*", "", t).strip()

# idempotent: drop any previous pass
for wid in sugg:
    sugg[wid] = [c for c in sugg[wid] if c.get("source_label") != LABEL]

added, skipped_multi, skipped_shared = 0, 0, 0
for ref, entry in lines.items():
    foots = entry.get("footnotes", {})
    # How many lines cite each marker? If a marker is cited by more than one
    # line, the note describes that whole group (9:2: "And your fear and your
    # terror" marks BOTH ומוראכם and וחתכם) — it is not the literal of any one
    # word, so it must not be attached to one.
    cited = {}
    for ln in entry.get("lines", []):
        for m in ln.get("marks", []):
            cited[m] = cited.get(m, 0) + 1
    for ln in entry.get("lines", []):
        for m in ln.get("marks", []):
            fn = foots.get(m)
            if not fn or fn["kind"] != "literal":
                continue
            if cited.get(m, 0) > 1:
                skipped_shared += 1       # note spans several lines -> not one word's literal
                continue
            if len(ln["positions"]) != 1:
                skipped_multi += 1        # which word? unknowable -> don't guess
                continue
            wid = pos2id.get((ref, ln["positions"][0]))
            if wid is None:
                continue
            text = strip(fn["text"])
            if not text:
                continue
            chips = sugg.setdefault(str(wid), [])
            at = 1 if chips and chips[0].get("base") else 0
            chips.insert(at, {"source_label": LABEL, "text": text, "recast": False})
            added += 1

json.dump(sugg, open(sugg_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("MAGIL FOOTNOTE -> LITERAL LAYER")
print(f"  literal chips attached (note on a single-word line): {added}")
print(f"  literal notes left as page-notes only (multi-word line, word unknowable): {skipped_multi}")
