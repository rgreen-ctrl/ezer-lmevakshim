"""Seed Layer 1 (Shoresh / root meaning) into Word.root_gloss from
data/root_gloss_noach.json — the clean Strong's primary sense. DRAFT only:
never touches certified rows, never touches translation/contextual. Idempotent.

    railway ssh python scripts/seed_root.py   # live (Postgres)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app, db
from app.models import Word

DATA = Path(__file__).resolve().parent.parent / "data" / "root_gloss_noach.json"


def main():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    app = create_app()
    with app.app_context():
        counts = {"seeded": 0, "kept_existing": 0, "skipped_missing": 0, "no_gloss": 0}
        for wid, rec in data.items():
            w = db.session.get(Word, int(wid))
            if w is None:
                counts["skipped_missing"] += 1
                continue
            # Fill BLANKS only. root_gloss is a new layer: on a certified word it
            # is simply empty, not a human decision, and leaving it NULL shows an
            # empty Shoresh field next to a chip that has the value. Never
            # overwrite a value already there (certified or not) — that WOULD be
            # touching someone's judgment.
            if w.root_gloss is not None:
                counts["kept_existing"] += 1
                continue
            if not rec.get("root_gloss"):
                counts["no_gloss"] += 1
                continue
            w.root_gloss = rec["root_gloss"]
            counts["seeded"] += 1
        db.session.commit()
        have = Word.query.filter(Word.root_gloss.isnot(None)).count()
        print("SEED ROOT:", json.dumps(counts), "| words_with_root_gloss:", have)


if __name__ == "__main__":
    main()
