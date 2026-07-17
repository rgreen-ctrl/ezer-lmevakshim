#!/usr/bin/env python3
"""The parsha pipeline runner — chains what exists, parameterized per parsha.

    python scripts/parsha_pipeline.py --check   # verify inputs, report stages

Stages (docs/PARSHA_PIPELINE.md is the authority):
  A. INPUTS (human/setup): morphhb <Book>.xml staged; Magil leaf range mapped;
     page originals downloaded; VISION CAPTURE banked per page into
     data/magil_lines/ (the irreducibly human step — the count gate makes it
     safe, nothing makes it automatic).
  B. SCRIPTED: verify_lines (count gate, HARD STOP on mismatch) -> build_lines
     -> build_layers (clean roots) -> magil_wins (prefill data + name map)
     -> build_sources (Onkelos/Rashi, license verified in-body; R-S English
     ONLY where PD: Bereishis+Shemos) -> build_hebrew_alternates ->
     build_ellipsis_collapse -> build_footnote_glosses -> rescore_lines.
  C. GATED (Rabbi Green's explicit OK, migrate -> deploy -> seed):
     import_corpus (new parsha words arrive as DRAFTS) -> seeders.

What CANNOT be scripted: the vision capture itself; leaf-range mapping eyes;
Rabbi Green's rulings; certification (never scripted, never will be).
"""
import argparse, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTED = ["verify_lines", "build_lines", "build_layers", "magil_wins",
            "build_sources", "build_hebrew_alternates",
            "build_ellipsis_collapse", "build_footnote_glosses", "rescore_lines"]

def run(name):
    print(f"\n=== {name} ===")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / f"{name}.py")])
    if r.returncode != 0:
        print(f"STOP: {name} failed — fix before continuing (count gate?)")
        sys.exit(1)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report stage status only")
    args = ap.parse_args()
    lines = list((ROOT / "data" / "magil_lines").glob("n*.json"))
    print(f"line captures banked: {len(lines)} pages")
    if args.check:
        print("scripted stages:", " -> ".join(SCRIPTED))
        print("human stages: leaf mapping, vision capture, rulings, certification")
        sys.exit(0)
    for s in SCRIPTED:
        run(s)
    print("\nPipeline complete. Gated next steps (need explicit OK):")
    print("  import_corpus -> deploy -> seed_* (drafts only, never certified)")
