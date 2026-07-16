#!/usr/bin/env python3
"""Cache Magil's page scans locally so the Desk can show the 1905 printing
inline, at a resolution that is actually readable.

Why not hotlink archive.org: their `_medium` derivative is only ~630px wide —
far too small to read a dense two-column page of pointed Hebrew — and a
content filter between the editor and archive.org silently kills the <img>.
Serving from our own origin fixes both, and doesn't depend on archive.org
staying up.

Source scans (2522x4036) are downscaled to a readable width and written to
app/static/magil_pages/n<leaf>.jpg. Run locally; the output is committed.

    python scripts/cache_pages.py
"""
import os, sys
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = r"C:\Users\RGBY\AppData\Local\Temp\claude\F--\358f8128-a2d1-49ad-8b08-206f9ba52342\scratchpad"
OUT = os.path.join(ROOT, "app", "static", "magil_pages")
LEAVES = range(500, 513)          # Noach: leaves 500-512
WIDTH = 1700                       # readable for pointed Hebrew; ~1/3 the bytes
QUALITY = 82

os.makedirs(OUT, exist_ok=True)
total = 0
for leaf in LEAVES:
    src = os.path.join(SRC, f"magil_n{leaf}.jpg")
    if not os.path.exists(src):
        print(f"  MISSING source for leaf {leaf}: {src}")
        continue
    im = Image.open(src)
    if im.mode != "RGB":
        im = im.convert("RGB")
    w, h = im.size
    if w > WIDTH:
        im = im.resize((WIDTH, round(h * WIDTH / w)), Image.LANCZOS)
    dst = os.path.join(OUT, f"n{leaf}.jpg")
    im.save(dst, "JPEG", quality=QUALITY, optimize=True, progressive=True)
    kb = os.path.getsize(dst) // 1024
    total += kb
    print(f"  n{leaf}.jpg  {w}x{h} -> {im.size[0]}x{im.size[1]}  {kb} KB")
print(f"cached {len(list(LEAVES))} pages, {total/1024:.1f} MB total -> app/static/magil_pages/")
