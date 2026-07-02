"""Seed the ladder and import corpus words.

The interlinear store (Ezer L'mevakshim editor app) is the master; this app
holds a read-only projection. Import accepts a CSV export of the interlinear
(one row per word) with columns:

    unit,kind,ref,pasuk_index,position,hebrew,translation,shoresh,certified

Usage:
    python3 scripts/import_corpus.py --csv path/to/noach.csv --track chumash
    python3 scripts/import_corpus.py --sample     # small demo corpus (dev only)

Words are imported with their certification status as exported; this script
never flips a certified flag on its own.
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app, db
from app.models import Track, Unit, Word

LADDER = [
    ("chumash", "Chumash — Noach & Lech Lecha", 1),
    ("avos", "Pirkei Avos", 2),
    ("eilu_metzios", "Eilu Metzios (Bava Metzia 21a–33b)", 3),
]

# A tiny certified demo set (Bereishis 6:9) for development only — real
# corpus comes from the interlinear export.
SAMPLE = [
    ("Noach", "parsha", "Bereishis 6:9", 1, 1, "אֵלֶּה", "these", "אלה"),
    ("Noach", "parsha", "Bereishis 6:9", 1, 2, "תּוֹלְדֹת", "the generations of", "ילד"),
    ("Noach", "parsha", "Bereishis 6:9", 1, 3, "נֹחַ", "Noach", None),
    ("Noach", "parsha", "Bereishis 6:9", 1, 4, "נֹחַ", "Noach", None),
    ("Noach", "parsha", "Bereishis 6:9", 1, 5, "אִישׁ", "a man", "אישׁ"),
    ("Noach", "parsha", "Bereishis 6:9", 1, 6, "צַדִּיק", "righteous", "צדק"),
    ("Noach", "parsha", "Bereishis 6:9", 1, 7, "תָּמִים", "perfect", "תמם"),
    ("Noach", "parsha", "Bereishis 6:9", 1, 8, "הָיָה", "he was", "היה"),
    ("Noach", "parsha", "Bereishis 6:9", 1, 9, "בְּדֹרֹתָיו", "in his generations", "דור"),
    ("Noach", "parsha", "Bereishis 6:9", 1, 10, "אֶת", "with", None),
    ("Noach", "parsha", "Bereishis 6:9", 1, 11, "הָאֱלֹהִים", "G-d", None),
    ("Noach", "parsha", "Bereishis 6:9", 1, 12, "הִתְהַלֶּךְ", "walked", "הלך"),
    ("Noach", "parsha", "Bereishis 6:9", 1, 13, "נֹחַ", "Noach", None),
    ("Noach", "parsha", "Bereishis 6:10", 2, 14, "וַיּוֹלֶד", "and he fathered", "ילד"),
    ("Noach", "parsha", "Bereishis 6:10", 2, 15, "נֹחַ", "Noach", None),
    ("Noach", "parsha", "Bereishis 6:10", 2, 16, "שְׁלֹשָׁה", "three", "שׁלשׁ"),
    ("Noach", "parsha", "Bereishis 6:10", 2, 17, "בָנִים", "sons", "בן"),
    ("Noach", "parsha", "Bereishis 6:10", 2, 18, "אֶת", "—", None),
    ("Noach", "parsha", "Bereishis 6:10", 2, 19, "שֵׁם", "Shem", None),
    ("Noach", "parsha", "Bereishis 6:10", 2, 20, "אֶת", "—", None),
    ("Noach", "parsha", "Bereishis 6:10", 2, 21, "חָם", "Cham", None),
    ("Noach", "parsha", "Bereishis 6:10", 2, 22, "וְאֶת", "and —", None),
    ("Noach", "parsha", "Bereishis 6:10", 2, 23, "יָפֶת", "Yefes", None),
]


def seed_ladder():
    for key, name, rung in LADDER:
        if not Track.query.filter_by(key=key).first():
            db.session.add(Track(key=key, name=name, rung_order=rung))
    db.session.commit()


def get_unit(track, name, kind):
    unit = Unit.query.filter_by(track_id=track.id, name=name).first()
    if unit is None:
        order = track.units.count() + 1
        unit = Unit(track_id=track.id, name=name, kind=kind, order_index=order)
        db.session.add(unit)
        db.session.flush()
    return unit


def import_csv(path, track_key):
    track = Track.query.filter_by(key=track_key).one()
    added = 0
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            unit = get_unit(track, row["unit"], row.get("kind", "parsha"))
            position = int(row["position"])
            if Word.query.filter_by(unit_id=unit.id, position=position).first():
                continue
            db.session.add(Word(
                unit_id=unit.id,
                ref=row["ref"],
                pasuk_index=int(row["pasuk_index"]),
                position=position,
                hebrew=row["hebrew"],
                translation=row["translation"],
                shoresh=row.get("shoresh") or None,
                certified=str(row.get("certified", "")).lower()
                in ("1", "true", "yes"),
            ))
            added += 1
    db.session.commit()
    return added


def import_sample():
    track = Track.query.filter_by(key="chumash").one()
    unit = get_unit(track, "Noach", "parsha")
    added = 0
    for _, kind, ref, pasuk, pos, hebrew, translation, shoresh in SAMPLE:
        if Word.query.filter_by(unit_id=unit.id, position=pos).first():
            continue
        db.session.add(Word(
            unit_id=unit.id, ref=ref, pasuk_index=pasuk, position=pos,
            hebrew=hebrew, translation=translation, shoresh=shoresh,
            certified=True,
        ))
        added += 1
    db.session.commit()
    return added


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", help="interlinear CSV export to import")
    parser.add_argument("--track", default="chumash", help="target track key")
    parser.add_argument("--sample", action="store_true",
                        help="seed the small demo corpus (development only)")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        seed_ladder()
        if args.sample:
            print(f"Imported {import_sample()} sample words.")
        elif args.csv:
            print(f"Imported {import_csv(args.csv, args.track)} words.")
        else:
            print("Ladder seeded. Pass --csv or --sample to import words.")


if __name__ == "__main__":
    main()
