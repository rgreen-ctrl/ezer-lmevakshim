"""Pre-fill Layer 2 (Word.translation) with Magil's ellipsis-collapsed value
where one exists — so the field already holds the best available answer and
Rabbi Green just approves. His instruction: 'the least work possible'.

DRAFTS ONLY: certified words are never touched. Every change writes a
GlossRevision row (audit; attributed to the admin who authorized the pass).
Idempotent — a word already holding the collapsed value is skipped.

    railway ssh python scripts/seed_literal_prefill.py
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import create_app, db
from app.models import Word, GlossRevision, Staff

DATA = Path(__file__).resolve().parent.parent / "data" / "suggestions_noach.json"
LABEL = "Magil (ellipsis collapsed)"

def main():
    sugg = json.loads(DATA.read_text(encoding="utf-8"))
    app = create_app()
    with app.app_context():
        admin = Staff.query.filter_by(role="admin").first()
        n = {"prefilled": 0, "skipped_certified": 0, "already": 0, "missing": 0}
        for wid, chips in sugg.items():
            val = next((c["text"] for c in chips if c.get("source_label") == LABEL), None)
            if not val:
                continue
            w = db.session.get(Word, int(wid))
            if w is None:
                n["missing"] += 1; continue
            if w.certified:
                n["skipped_certified"] += 1; continue
            if (w.translation or "") == val:
                n["already"] += 1; continue
            db.session.add(GlossRevision(word_id=w.id, editor_id=admin.id,
                                         old_gloss=w.translation or "",
                                         new_gloss=val))
            w.translation = val
            n["prefilled"] += 1
        db.session.commit()
        print("PREFILL LITERAL (Magil collapsed):", json.dumps(n))

if __name__ == "__main__":
    main()
