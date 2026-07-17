#!/usr/bin/env python3
"""Propose per-word literals by splitting Magil's LINE — only where the split
is certain. Magil translates line-by-line, not word-by-word, so a per-word
literal can only ever be a PROPOSAL, and only when it is unambiguous.

The rules, in order:
  1. Bracketed [..] and parenthesized (..) text is English Magil SUPPLIED —
     it has no Hebrew behind it ("[are]", "[was]", "(his)"). It never maps to
     a Hebrew word, is never offered as a literal, and is never counted when
     checking alignment. Stripped before anything else.
  2. An ellipsis marks a split construction ("a … man" over נח איש צדיק) —
     discontinuous English. Propose nothing for that line.
  3. Propose only on an exact 1:1, in-order match of the remaining English
     words to the line's Hebrew words. A tight article/preposition reduction
     (the/a/an/of) is allowed ONLY when it lands exactly. Otherwise: nothing.
  4. Output is a CHIP ("Magil (split)") on the literal layer — never applied.
  5. Words with no proposal keep their existing value and are marked, so it is
     visible that the literal is the lexicon's and not Magil's.

A Hebrew word with no English under it is honest. A Hebrew word with the WRONG
English under it teaches a bochur something false. Silence wins.
"""
import json, os, re
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def L(p): return json.load(open(p, encoding="utf-8-sig"))

lines = L(os.path.join(ROOT, "app", "static", "magil_lines.json"))
lw = L(os.path.join(ROOT, "data", "staging", "live_words.json"))
sugg_path = os.path.join(ROOT, "data", "suggestions_noach.json")
sugg = L(sugg_path)

LABEL = "Magil (split)"
pos2id = {(w["ref"], w["pos"]): w["id"] for w in lw}

SUPPLIED = re.compile(r"\[[^\]]*\]|\([^)]*\)")      # rule 1
ELLIPSIS = re.compile(r"…|\.\.\.")                   # rule 2
SUPS = "¹²³⁴⁵⁶⁷⁸⁹"
DROP = {"the", "a", "an", "of"}                      # rule 3, tight reduction

def tokens(en):
    en = SUPPLIED.sub(" ", en)                       # rule 1: supplied text gone
    en = "".join(ch for ch in en if ch not in SUPS)  # footnote markers aren't words
    return re.findall(r"[A-Za-z][A-Za-z'\-]*", en)

LABEL_ELL = "Magil (ellipsis collapsed)"

# verb positions from morphhb, for the one-word collapse rule
sys_path_added = False
import sys as _sys
_sys.path.insert(0, os.path.join(ROOT, "scripts"))
from build_contextual import parse_morphhb, ref_to_cv
_morph = parse_morphhb()
is_verb = {}
for _ref_cv, _mws in _morph.items():
    for _i, _mw in enumerate(_mws, start=1):
        pass  # positions are unit-global; map via live words below

# live positions are unit-global; morph is per-verse in order — align by verse
from collections import defaultdict as _dd
_byref = _dd(list)
for _w in lw:
    _byref[_w["ref"]].append(_w)
for _ref, _ws in _byref.items():
    _ws.sort(key=lambda w: w["pos"])
    _mws = _morph.get(ref_to_cv(_ref), [])
    if len(_mws) == len(_ws):
        for _w, _mw in zip(_ws, _mws):
            is_verb[(_ref, _w["pos"])] = bool(_mw.get("is_verb"))

# idempotent
for wid in sugg:
    sugg[wid] = [c for c in sugg[wid]
                 if c.get("source_label") not in (LABEL, LABEL_ELL)]

why = Counter()
proposed = {}
collapsed = {}
for ref, entry in lines.items():
    for ln in entry.get("lines", []):
        pos = ln.get("positions", [])
        en = ln.get("en", "")
        n = len(pos)
        if not n:
            continue
        if ELLIPSIS.search(en):
            # THE ONE-WORD COLLAPSE RULE (confirmed by Rabbi Green): collapse an
            # ellipsis only when, after accounting for the straddled material,
            # exactly ONE Hebrew word remains to receive the literal. For a
            # 2-word line where exactly one word is the verb and the other is
            # the straddling subject ("and … was filled" over ותמלא הארץ), the
            # collapsed English is the verb's literal. 6:9's "a … man" over
            # THREE words stays refused — still a positional guess.
            if n == 2:
                verbs = [i for i, p in enumerate(pos) if is_verb.get((ref, p))]
                if len(verbs) == 1:
                    toks = tokens(en)
                    if toks:
                        wid = pos2id.get((ref, pos[verbs[0]]))
                        if wid is not None:
                            collapsed[wid] = " ".join(toks)
                            why["PROPOSED: ellipsis collapsed (one word left to receive)"] += 1
                            why["skipped: ellipsis-line partner word (straddled material)"] += n - 1
                            continue
            why["skipped: ellipsis (split construction, not collapsible)"] += n
            continue
        # A footnote mark only creates AMBIGUITY on a multi-word line (which
        # word does the note attach to?) — and those are refused anyway. On a
        # one-word line ("⁴rooms" over קנים) there is nothing to be ambiguous
        # about, so the mark is simply stripped and the literal stands.
        toks = tokens(en)
        if not toks:
            why["skipped: line is entirely supplied text ([..]/(..))"] += n
            continue
        # THE ONLY SAFE CASE: a line covering exactly one Hebrew word. Then the
        # line's English *is* that word's literal — no alignment assumption is
        # made, so no order can be got wrong.
        #
        # Multi-word lines are refused on principle. A count match does NOT prove
        # alignment: "Noah [was] a just man," is 3 English words over 3 Hebrew
        # (נח איש צדיק), but English puts the adjective FIRST and Hebrew puts it
        # second — a positional split yields איש->"just", צדיק->"man". Both wrong.
        # Nothing in the counts reveals that. So: silence.
        if n != 1:
            why["skipped: multi-word line (English/Hebrew order not provable)"] += n
            continue
        wid = pos2id.get((ref, pos[0]))
        if wid is None:
            continue
        proposed[wid] = " ".join(toks)
        why["PROPOSED: line covers exactly one Hebrew word"] += n

for wid, tok in proposed.items():
    chips = sugg.setdefault(str(wid), [])
    at = 1 if chips and chips[0].get("base") else 0
    chips.insert(at, {"source_label": LABEL, "text": tok, "recast": False})
for wid, tok in collapsed.items():
    chips = sugg.setdefault(str(wid), [])
    at = 1 if chips and chips[0].get("base") else 0
    chips.insert(at, {"source_label": LABEL_ELL, "text": tok, "recast": False})

json.dump(sugg, open(sugg_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

total = len(lw)
print("MAGIL PER-WORD SPLIT PROPOSALS (chips only — never applied)")
print(f"  words total: {total}")
print(f"  words WITH a confident Magil-split proposal: {len(proposed)}")
print(f"  words with NO proposal (left on the lexicon value): {total - len(proposed)}")
print("  why:")
for k, v in why.most_common():
    print(f"    {v:5}  {k}")
print("\n  samples:")
id2 = {w["id"]: w for w in lw}
for wid in list(proposed)[:10]:
    w = id2[wid]
    print(f"    {w['ref']:16} {w['he']:12} -> {proposed[wid]!r}")
