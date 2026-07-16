#!/usr/bin/env python3
"""Build the line-based Magil model from the per-page line captures. Assigns
each line the consecutive Hebrew word POSITIONS it covers (line word-counts
sum to the pasuk's word count, checked by verify_lines.py first). Output drives
the Desk's one line-grouped view: per-word literal beneath each Hebrew word +
Magil's flowing line English across the group.

Output (committed):
  app/static/magil_lines.json   ref -> {leaf, page_url, lines:[{en, positions, footnotes}]}
"""
import json, os, glob
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STG = os.path.join(ROOT, "data", "staging")
IA = "magilslinearscho00magirich"

def L(p): return json.load(open(p, encoding="utf-8-sig"))

lw = L(os.path.join(STG, "live_words.json"))
pos_by_cv = defaultdict(list)
for w in lw:
    pos_by_cv[w["ref"].split()[-1]].append(w["pos"])
for cv in pos_by_cv:
    pos_by_cv[cv].sort()

# merge captures (partials across pages accumulate in ref order by leaf desc =
# page order; files are named n512..n500, higher leaf = earlier text)
merged = {}
foots = {}
leaf_of = {}
for f in sorted(glob.glob(os.path.join(ROOT, "data", "magil_lines", "n*.json")),
                key=lambda p: -int(os.path.basename(p)[1:-5])):
    for cv, entry in L(f).items():
        merged.setdefault(cv, []).extend(entry["lines"])
        leaf_of.setdefault(cv, entry.get("leaf"))
        if entry.get("footnotes"):
            foots.setdefault(cv, {}).update(entry["footnotes"])

out = {}
skipped = []
for cv, lines in merged.items():
    positions = pos_by_cv.get(cv, [])
    total = sum(n for _, n in lines)
    if total != len(positions):
        skipped.append((cv, len(positions), total))
        continue
    result, i = [], 0
    for en, n in lines:
        result.append({"en": en, "positions": positions[i:i + n]})
        i += n
    leaf = leaf_of.get(cv)
    # Served from our own origin (app/static/magil_pages), not hotlinked: the
    # archive.org derivative is unreadably small and a content filter can block
    # it outright. `source_url` keeps the provenance link for attribution.
    out[f"Bereishis {cv}"] = {
        "leaf": leaf,
        "page_url": f"/magil_pages/n{leaf}.jpg" if leaf else None,
        "source_url": f"https://archive.org/details/{IA}/page/n{leaf}" if leaf else None,
        "lines": result,
        "footnotes": foots.get(cv, {}),
    }

json.dump(out, open(os.path.join(ROOT, "app", "static", "magil_lines.json"), "w",
                    encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"line model: {len(out)} pesukim built, {len(skipped)} skipped (count mismatch: {skipped})")
print(f"6:9 lines: {[l['en'] for l in out.get('Bereishis 6:9',{}).get('lines',[])]}")
