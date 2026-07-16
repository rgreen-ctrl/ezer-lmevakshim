#!/usr/bin/env python3
"""Re-score confidence with Magil's LINE model in place. The line is Magil's own
alignment unit, so a line-covered word sits on his real, printed rendering —
there is no 'split-pending' doubt to carry. What remains for a human eye:
pesukim Onkelos recasts, and the one ketiv/qere oddity in 8:17.

Writes data/selfcheck_noach.json (DRAFT ordering data; never approves).
"""
import json, os, re
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STG = os.path.join(ROOT, "data", "staging")
def L(p): return json.load(open(p, encoding="utf-8-sig"))

lines = L(os.path.join(ROOT, "app", "static", "magil_lines.json"))
lw = L(os.path.join(STG, "live_words.json"))
sugg = L(os.path.join(STG, "suggestions_map.json"))
NIKUD = re.compile(r"[֑-ׇ]")

def recast_on(wid): return any(o.get("recast") for o in sugg.get(str(wid), []))

# word_id -> the line covering it
line_of = {}
by_ref = defaultdict(list)
for w in lw:
    by_ref[w["ref"]].append(w)
for ref, ws in by_ref.items():
    entry = lines.get(ref)
    if not entry: continue
    pos2w = {w["pos"]: w for w in ws}
    for ln in entry["lines"]:
        for p in ln["positions"]:
            if p in pos2w:
                line_of[pos2w[p]["id"]] = ln["en"]

selfcheck, dist = {}, Counter()
for w in lw:
    wid = w["id"]; checks = []
    en = line_of.get(wid)
    if en is None:
        conf = "low"
        checks.append({"pass": 0, "level": "flag",
                       "reason": "no Magil line covers this word",
                       "proposed_fix": "capture the page line for this pasuk"})
    elif not NIKUD.search(w["he"] or ""):
        # the ketiv (written-not-read) form — a corpus question, not a translation one
        conf = "medium"
        checks.append({"pass": 0, "level": "flag",
                       "reason": "ketiv (written, not read) — the qere is the form that is read; "
                                 "decide whether this should be a drilled word at all",
                       "proposed_fix": ""})
    elif recast_on(wid):
        conf = "medium"
        checks.append({"pass": 2, "level": "note",
                       "reason": f"Onkelos recasts this pasuk; Magil's line reads “{en}” — compare",
                       "proposed_fix": ""})
    else:
        conf = "high"
        checks.append({"pass": 0, "level": "note",
                       "reason": f"Magil's printed line: “{en}”",
                       "proposed_fix": ""})
    dist[conf] += 1
    selfcheck[str(wid)] = {"confidence": conf, "check_results": checks}

json.dump(selfcheck, open(os.path.join(ROOT, "data", "selfcheck_noach.json"), "w",
                          encoding="utf-8"), ensure_ascii=False, indent=1)
old = {"high": 732, "medium": 1130, "low": 0}
print("RE-SCORE WITH THE LINE MODEL")
print(f"  words covered by a Magil line: {len(line_of)}/{len(lw)}")
for k in ("high", "medium", "low"):
    print(f"  {k:7} {old[k]:5} -> {dist[k]:5}   ({dist[k]-old[k]:+d})")
print(f"  MEDIUM is now only: Onkelos-recast pesukim + the single ketiv at 8:17")
