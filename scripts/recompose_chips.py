#!/usr/bin/env python3
"""Re-compose the Binyan and Morphology chips from the CLEANED root gloss.

Both composers ran BEFORE the root reseed, so they are still built on the
Strong's KJV-usage dumps: וַתִּמָּלֵא showed Binyan "was accomplish, confirm /
accomplish, confirm itself" and Morphology "and accomplish, confirm", because
its root *was* "accomplish, confirm" when those chips were made. The shoresh
chip and the interlinear now read "fill"; these were simply never rebuilt.

Composing from Layer 1 instead — which is the point of cleaning Layer 1: fix
the root and everything composed from it comes out right. Reuses the existing
composer and binyan transforms rather than re-implementing them, so the chips
stay consistent with how they were always built.

Idempotent. Chips only — nothing is applied or certified.
"""
import json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build_contextual import parse_morphhb, compose, ref_to_cv   # affix composer
from build_suggestions import BINYAN                              # binyan transforms

def L(p): return json.loads(Path(p).read_text(encoding="utf-8-sig"))

live = L(ROOT / "data" / "staging" / "live_words.json")
roots = L(ROOT / "data" / "root_gloss_noach.json")
sugg_path = ROOT / "data" / "suggestions_noach.json"
sugg = L(sugg_path)
morph = parse_morphhb()

byverse = {}
for w in live:
    byverse.setdefault(ref_to_cv(w["ref"]), []).append(w)
for v in byverse.values():
    v.sort(key=lambda w: w["pos"])

MORPH_LABEL = "Morphology (morphhb)"
stats = {"morphology_recomposed": 0, "binyan_recomposed": 0,
         "skipped_no_root": 0, "skipped_unaligned": 0}
samples = []

for cv, lwords in sorted(byverse.items()):
    mwords = morph.get(cv, [])
    aligned = len(mwords) == len(lwords)
    if not aligned:
        stats["skipped_unaligned"] += len(lwords)
        continue
    for i, lw in enumerate(lwords):
        wid = str(lw["id"])
        root = (roots.get(wid) or {}).get("root_gloss")
        if not root:
            stats["skipped_no_root"] += 1
            continue
        mw = mwords[i]
        chips = sugg.get(wid, [])
        # Morphology: the affix-folded draft, now from the clean root.
        newm = compose(mw["prefixes"], mw["suffix"], root, mw["is_verb"], mw["is_np"])
        # Binyan: the non-qal nuance, now from the clean root.
        newb = None
        cm = mw.get("content_morph") or ""
        if cm.startswith("V") and len(cm) > 1:
            nm = BINYAN.get(cm[1])
            if nm:
                newb = (f"Binyan: {nm[0]}", nm[1](root))
        out = []
        for c in chips:
            lab = c.get("source_label", "")
            if lab == MORPH_LABEL and newm:
                if c["text"] != newm:
                    samples.append((lw["ref"], lw["he"], lab, c["text"], newm))
                c = dict(c, text=newm); stats["morphology_recomposed"] += 1
            elif lab.startswith("Binyan:"):
                if newb:
                    if c["text"] != newb[1]:
                        samples.append((lw["ref"], lw["he"], lab, c["text"], newb[1]))
                    c = dict(c, source_label=newb[0], text=newb[1])
                    stats["binyan_recomposed"] += 1
                else:
                    continue          # no longer a non-qal verb: drop the chip
            out.append(c)
        sugg[wid] = out

sugg_path.write_text(json.dumps(sugg, ensure_ascii=False, indent=1), encoding="utf-8")
print("RE-COMPOSE CHIPS FROM THE CLEAN ROOT")
for k, v in stats.items():
    print(f"  {k}: {v}")
print("\n  changed (old -> new):")
for ref, he, lab, old, new in samples[:12]:
    print(f"    {ref:15} {he:12} [{lab}]\n        {old!r}\n     -> {new!r}")
