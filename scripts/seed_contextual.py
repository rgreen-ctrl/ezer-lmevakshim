"""Seed DRAFT contextual translations from data/contextual_noach.json.

DRAFTS ONLY. Never touches the literal `translation`, never touches
`certified` rows, and never overwrites a contextual value that already exists
(so an editor's hand-edit is preserved on re-run). Idempotent.

    railway ssh python scripts/seed_contextual.py   # live (Postgres)
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
        counts = {"seeded": 0, "skipped_certified": 0,
                  "skipped_existing": 0, "skipped_missing": 0}
        for wid, rec in data.items():
            w = db.session.get(Word, int(wid))
            if w is None:
                counts["skipped_missing"] += 1
                continue
            if w.certified:
                counts["skipped_certified"] += 1
                continue
            if w.contextual_translation is not None:
                counts["skipped_existing"] += 1   # preserve editor edits
                continue
            w.contextual_translation = (rec.get("contextual") or "").strip() or None
            w.contextual_flagged = bool(rec.get("flagged"))
            w.contextual_note = (rec.get("note") or "").strip() or None
            counts["seeded"] += 1
        db.session.commit()
        flagged = Word.query.filter_by(contextual_flagged=True).count()
        have = Word.query.filter(Word.contextual_translation.isnot(None)).count()
        print("SEED:", json.dumps(counts),
              "| words_with_contextual:", have, "| flagged:", flagged)


if __name__ == "__main__":
    main()
