"""Seed per-word confidence + check_results from data/selfcheck_noach.json.
Ordering metadata only: never touches gloss/contextual/certified, never
approves anything. Skips certified rows. Idempotent.

    railway ssh python scripts/seed_selfcheck.py   # live (Postgres)
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app, db
from app.models import Word

DATA = Path(__file__).resolve().parent.parent / "data" / "selfcheck_noach.json"


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
            # confidence/check_results are REFERENCE (ordering) data, not the
            # certified content — seed on certified words too so a reopened word
            # still shows why it was flagged.
            w.confidence = rec["confidence"]
            w.check_results = json.dumps(rec["check_results"], ensure_ascii=False)
            counts["seeded"] += 1
        db.session.commit()
        dist = {lvl: Word.query.filter_by(confidence=lvl).count()
                for lvl in ("high", "medium", "low")}
        print("SEED SELFCHECK:", json.dumps(counts), "| live distribution:", json.dumps(dist))


if __name__ == "__main__":
    main()
