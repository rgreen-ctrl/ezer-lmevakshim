#!/usr/bin/env python3
"""Verify Magil line captures: each pasuk's line word-counts must sum to the
morphhb word count. Partial pesukim (split across a page break) are merged by
ref before checking. Reports OK / mismatches per page so a bad read is caught."""
import json, os, glob, xml.etree.ElementTree as ET
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STG = os.path.join(ROOT, "data", "staging")
NS = "{http://www.bibletechnologies.net/2003/OSIS/namespace}"

# morphhb counts for Noach
tree = ET.parse(os.path.join(STG, "morphhb_Gen.xml"))
mcount = {}
for v in tree.getroot().iter(NS + "verse"):
    oid = v.get("osisID")
    if not oid: continue
    _, c, vs = oid.split("."); c = int(c); vs = int(vs)
    if not ((c == 6 and vs >= 9) or (7 <= c <= 10) or (c == 11 and vs <= 32)):
        continue
    mcount[f"{c}:{vs}"] = sum(1 for _ in v.iter(NS + "w"))

# merge every captured page, summing line-word-counts per ref
summed = defaultdict(int)
lines_by_cv = {}
for f in sorted(glob.glob(os.path.join(ROOT, "data", "magil_lines", "n*.json"))):
    data = json.load(open(f, encoding="utf-8-sig"))
    for cv, entry in data.items():
        summed[cv] += sum(n for _, n in entry["lines"])
        lines_by_cv.setdefault(cv, []).extend(entry["lines"])

ok = bad = 0
for cv in sorted(summed, key=lambda x: (int(x.split(":")[0]), int(x.split(":")[1]))):
    exp = mcount.get(cv)
    got = summed[cv]
    if exp == got:
        ok += 1
    else:
        bad += 1
        print(f"  MISMATCH {cv}: morphhb={exp} lines={got}")
print(f"captured pesukim: {len(summed)} | OK: {ok} | mismatches: {bad}")
print(f"remaining uncaptured: {len(mcount) - len(summed)}")
