"""Seed DRAFT contextual translations from Magil (data/contextual_noach.json),
REPLACING the earlier mechanical draft. Unlike seed_contextual.py this
overwrites an existing contextual value — the whole point of the Magil rollout
is to replace dictionary-junk drafts with Magil's real English. Still DRAFTS
ONLY: never touches the literal `translation`, never touches certified rows.
Idempotent.

    railway ssh python scripts/seed_magil_contextual.py   # live (Postgres)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app, db
from app.models import Word

DATA = Path(__file__).resolve().parent.parent / "data" / "contextual_noach.json"


def main():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    app = create_app()
    with app.app_context():
        counts = {"seeded": 0, "skipped_certified": 0, "skipped_missing": 0}
        for wid, rec in data.items():
            w = db.session.get(Word, int(wid))
            if w is None:
                counts["skipped_missing"] += 1
                continue
            if w.certified:
                counts["skipped_certified"] += 1   # never touch certified content
                continue
            val = (rec.get("contextual") or "").strip()
            w.contextual_translation = val or None
            w.contextual_flagged = bool(rec.get("flagged"))
            note = (rec.get("note") or "").strip()
            w.contextual_note = note or None
            counts["seeded"] += 1
        db.session.commit()
        have = Word.query.filter(Word.contextual_translation.isnot(None)).count()
        print("SEED MAGIL CONTEXTUAL:", json.dumps(counts),
              "| words_with_contextual:", have)


if __name__ == "__main__":
    main()
