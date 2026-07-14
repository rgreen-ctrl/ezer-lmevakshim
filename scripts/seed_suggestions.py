"""Seed grounded suggestion sets from data/suggestions_noach.json into
Word.suggestions (JSON text). Reference data only: never touches the literal
gloss, contextual draft, or certified rows. Idempotent (overwrites the
reference set on re-run). Skips certified rows to honour the never-touch rule.

    railway ssh python scripts/seed_suggestions.py   # live (Postgres)
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app, db
from app.models import Word

DATA = Path(__file__).resolve().parent.parent / "data" / "suggestions_noach.json"


def main():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    app = create_app()
    with app.app_context():
        counts = {"seeded": 0, "skipped_certified": 0, "skipped_missing": 0}
        for wid, opts in data.items():
            w = db.session.get(Word, int(wid))
            if w is None:
                counts["skipped_missing"] += 1
                continue
            if w.certified:
                counts["skipped_certified"] += 1
                continue
            w.suggestions = json.dumps(opts, ensure_ascii=False)
            counts["seeded"] += 1
        db.session.commit()
        have = Word.query.filter(Word.suggestions.isnot(None)).count()
        print("SEED SUGG:", json.dumps(counts), "| words_with_suggestions:", have)


if __name__ == "__main__":
    main()
