#!/usr/bin/env python3
"""Ellipsis collapse — the one-word rule (confirmed by Rabbi Green).

Magil's printed LINES never contain ellipses; the '…' strings live in the old
per-word capture (the Magil chips / contextual values), where each ellipsis
string is already assigned to exactly ONE Hebrew word — the gap marks material
straddled by OTHER words ("and … was filled" on ותמלא, where הארץ fills the
gap). So exactly one word remains to receive the collapsed literal, which is
precisely the confirmed rule. Collapse = remove the gap marker and rejoin.

Offered as a chip, "Magil (ellipsis collapsed)", on the LITERAL layer.
Never auto-applied. Brackets/parens still never map to a Hebrew word: any
bracketed text is stripped before offering.
"""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sugg_path = ROOT / "data" / "suggestions_noach.json"
sugg = json.loads(sugg_path.read_text(encoding="utf-8-sig"))
lw = {str(w["id"]): w for w in json.loads(
    (ROOT / "data" / "staging" / "live_words.json").read_text(encoding="utf-8-sig"))}

LABEL = "Magil (ellipsis collapsed)"
ELL = re.compile(r"\s*(…|\.\.\.)\s*")
SUPPLIED = re.compile(r"\[[^\]]*\]|\([^)]*\)")

added = 0
samples = []
for wid, chips in sugg.items():
    chips = [c for c in chips if c.get("source_label") != LABEL]   # idempotent
    base = next((c for c in chips if c.get("source_label") == "Magil (linear, 1905)"), None)
    if base and ELL.search(base.get("text") or ""):
        txt = SUPPLIED.sub(" ", base["text"])          # brackets never map
        txt = ELL.sub(" ", txt)                        # close the gap
        txt = re.sub(r"\s{2,}", " ", txt).strip(" ,.;:")
        # A per-word literal is SHORT. The old grouped spans assigned a whole
        # phrase to every word they covered ('And … did Noah according to all
        # that commanded him God…' on each of 9 words) — collapsing those would
        # put a sentence under a single word. Cap at 4 English words; beyond
        # that it isn't one word's literal, so offer nothing.
        if txt and len(txt.split()) <= 4:
            at = 1 if chips and chips[0].get("base") else 0
            chips.insert(at, {"source_label": LABEL, "text": txt, "recast": False})
            added += 1
            if len(samples) < 8:
                w = lw.get(wid, {})
                samples.append((w.get("ref"), w.get("he"), base["text"], txt))
    sugg[wid] = chips

sugg_path.write_text(json.dumps(sugg, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"ELLIPSIS COLLAPSE: {added} chips offered (literal layer, never applied)")
for ref, he, old, new in samples:
    print(f"  {ref:16} {he:14} {old!r} -> {new!r}")
