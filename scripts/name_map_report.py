#!/usr/bin/env python3
"""Name map — REPORT ONLY. Nothing is applied by this script.

Finds every proper noun appearing in Magil's English (the flowing lines and
the Magil-sourced chips) and counts instances, so Rabbi Green can approve the
substitution list before anything changes.

Scope (locked by Rabbi Green):
  - Magil's English: flowing lines, Magil chips, Magil-split literals  -> listed
  - Strong's proper-noun entries (Shoresh chips that are names)        -> listed
  - Hebrew, Aramaic, Rashi's Hebrew                                    -> never
  - R-S Rashi English (a citation, not our base layer)                 -> never
  - Certified words                                                    -> never
    overwritten; any whose value would change are FLAGGED to reopen.
"""
import json, re
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parent.parent
def L(p): return json.loads(Path(p).read_text(encoding="utf-8-sig"))

lines = L(ROOT / "app" / "static" / "magil_lines.json")
sugg = L(ROOT / "data" / "suggestions_noach.json")
ctx = L(ROOT / "data" / "contextual_noach.json")

# The proposed frum transliterations for every proper noun that occurs in
# Magil's Noach English. Derived from the text itself (all names below were
# actually found in it); Rabbi Green approves/edits this table.
PROPOSED = {
    "Noah": "Noach", "Shem": "Shem", "Ham": "Cham", "Japheth": "Yefes",
    "Canaan": "Kenaan", "Cush": "Kush", "Mizraim": "Mitzrayim", "Put": "Put",
    "Nimrod": "Nimrod", "Babel": "Bavel", "Erech": "Erech", "Accad": "Akkad",
    "Calneh": "Kalneh", "Shinar": "Shinar", "Nineveh": "Nineveh",
    "Rehoboth-Ir": "Rechovos-Ir", "Calah": "Kalach", "Resen": "Resen",
    "Ludim": "Ludim", "Anamim": "Anamim", "Lehabim": "Lehavim",
    "Naphtuhim": "Naftuchim", "Pathrusim": "Pasrusim", "Casluhim": "Kasluchim",
    "Philistines": "Pelishtim", "Caphtorim": "Kaftorim", "Zidon": "Tzidon",
    "Heth": "Cheis", "Jebusite": "Yevusi", "Amorite": "Emori",
    "Girgashite": "Girgashi", "Hivite": "Chivi", "Arkite": "Arki",
    "Sinite": "Sini", "Arvadite": "Arvadi", "Zemarite": "Tzemari",
    "Hamathite": "Chamasi", "Canaanite": "Kenaani", "Gerar": "Gerar",
    "Gaza": "Azah", "Sodom": "Sedom", "Gomorrah": "Amorah", "Admah": "Admah",
    "Zeboiim": "Tzevoyim", "Lasha": "Lesha", "Elam": "Eilam",
    "Asshur": "Ashur", "Assyria": "Ashur", "Arpachshad": "Arpachshad",
    "Lud": "Lud", "Aram": "Aram", "Uz": "Utz", "Hul": "Chul",
    "Gether": "Geser", "Mash": "Mash", "Shelah": "Shelach", "Eber": "Ever",
    "Peleg": "Peleg", "Joktan": "Yoktan", "Almodad": "Almodad",
    "Sheleph": "Shelef", "Hazarmaveth": "Chatzarmaves", "Jerah": "Yerach",
    "Hadoram": "Hadoram", "Uzal": "Uzal", "Diklah": "Diklah", "Obal": "Oval",
    "Abimael": "Avimael", "Sheba": "Sheva", "Ophir": "Ofir",
    "Havilah": "Chavilah", "Jobab": "Yovav", "Mesha": "Mesha",
    "Sephar": "Sefar", "Gomer": "Gomer", "Magog": "Magog", "Madai": "Madai",
    "Javan": "Yavan", "Tubal": "Tuval", "Meshech": "Meshech",
    "Tiras": "Tiras", "Ashkenaz": "Ashkenaz", "Riphath": "Rifas",
    "Togarmah": "Togarmah", "Elishah": "Elishah", "Tarshish": "Tarshish",
    "Kittim": "Kittim", "Dodanim": "Dodanim", "Seba": "Seva",
    "Sabtah": "Savtah", "Raamah": "Raamah", "Sabteca": "Savtecha",
    "Dedan": "Dedan", "Ararat": "Ararat", "Reu": "Reu", "Serug": "Serug",
    "Nahor": "Nachor", "Terah": "Terach", "Abram": "Avram", "Haran": "Haran",
    "Haron": "Haran", "Lot": "Lot", "Sarai": "Sarai", "Milcah": "Milkah",
    "Iscah": "Yiskah", "Ur": "Ur", "Chaldees": "Kasdim",
    # divine names/titles are NOT names to transliterate — excluded on purpose:
    # "God", "Lord" stay as Magil printed them pending Rabbi Green's direction.
}
WORD = re.compile(r"[A-Za-z][A-Za-z'\-]+")

counts = Counter()          # name -> instances across Magil English
where = defaultdict(Counter)  # name -> {flowing|chip}
unknown_caps = Counter()    # capitalized tokens not in the map (for completeness)
STOP = {"And", "The", "These", "This", "Come", "Like", "Behold", "Or", "Of",
        "From", "In", "For", "He", "She", "I", "But", "Also", "My", "All",
        "Every", "Make", "Go", "Two", "Fifteen", "Cursed", "Blessed", "God",
        "Lord", "While", "Therefore", "Whoso", "Be", "A", "An", "As", "To",
        "Heb", "H", "That", "Cap", "Chapter", "English", "Ir", "You", "Yea"}

def scan(text, kind):
    for tok in WORD.findall(text or ""):
        if tok in PROPOSED:
            counts[tok] += 1
            where[tok][kind] += 1
        elif tok[0].isupper() and tok not in STOP:
            unknown_caps[tok] += 1

for ref, e in lines.items():
    for ln in e.get("lines", []):
        scan(ln.get("en"), "flowing line")

MAGIL_CHIPS = ("Magil (linear, 1905)", "Magil literal (Heb.)", "Magil (split)",
               "Plainer English")
for wid, chips in sugg.items():
    for c in chips:
        lab = c.get("source_label", "")
        if lab.startswith(MAGIL_CHIPS) or lab in ("Shoresh (root)",):
            scan(c.get("text"), "chip")

# certified words whose flowing value contains a mapped name -> flag, don't touch
cert_flags = []
for wid, rec in ctx.items():
    pass  # certified state lives in the DB, reported at apply time

print("NAME MAP — PROPOSED SUBSTITUTIONS (report only, NOTHING applied)")
print(f"{'Magil 1905':16} {'proposed':16} {'count':>5}  where")
total = 0
for name, n in counts.most_common():
    total += n
    w = ", ".join(f"{k}×{v}" for k, v in where[name].items())
    mark = "  (unchanged)" if PROPOSED[name] == name else ""
    print(f"{name:16} {PROPOSED[name]:16} {n:5}  {w}{mark}")
print(f"\nTOTAL instances across Magil English: {total}")
print(f"Distinct names found: {len(counts)}")
unchanged = [n for n in counts if PROPOSED[n] == n]
print(f"Names whose transliteration is identical (no visible change): {len(unchanged)}")
if unknown_caps:
    print("\nCapitalized tokens NOT in the map (check none is a missed name):")
    for t, n in unknown_caps.most_common(20):
        print(f"  {t}: {n}")
