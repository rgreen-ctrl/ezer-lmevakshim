"""Idempotent migration: add the contextual-translation columns to `words`.

create_all() adds them on a fresh database; an existing Postgres/SQLite table
needs an explicit ALTER. Uses the inspector (not "ADD COLUMN IF NOT EXISTS")
so it is portable across both backends. Safe to re-run.

    railway ssh python scripts/migrate_contextual.py   # live (Postgres)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, text

from app import create_app, db

COLUMNS = {
    "contextual_translation": "VARCHAR(255)",
    "contextual_flagged": "BOOLEAN NOT NULL DEFAULT FALSE",
    "contextual_note": "VARCHAR(255)",
    "suggestions": "TEXT",
    "confidence": "VARCHAR(10)",
    "check_results": "TEXT",
}


def main():
    app = create_app()
    with app.app_context():
        db.create_all()  # fresh databases get every column here
        existing = {c["name"] for c in inspect(db.engine).get_columns("words")}
        dialect = db.engine.dialect.name
        added = []
        for col, ddl in COLUMNS.items():
            if col in existing:
                continue
            if dialect == "sqlite" and ddl.startswith("BOOLEAN"):
                ddl = "BOOLEAN NOT NULL DEFAULT 0"
            db.session.execute(text(f"ALTER TABLE words ADD COLUMN {col} {ddl}"))
            added.append(col)
        db.session.commit()
        print(f"dialect={dialect} added={added or 'none (already present)'}")


if __name__ == "__main__":
    main()
