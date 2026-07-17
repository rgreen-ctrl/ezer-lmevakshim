"""Seed Magil-wins prefill (L1 root_gloss, L2 translation). Drafts only:
certified words are FLAGGED in output, never written. GlossRevision on every
change.   railway ssh python scripts/seed_magil_wins.py"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import create_app, db
from app.models import Word, GlossRevision, Staff
data = json.loads((Path(__file__).resolve().parent.parent/"data"/"magil_prefill.json").read_text("utf-8"))
app = create_app()
with app.app_context():
    admin = Staff.query.filter_by(role="admin").first()
    n = {"l1": 0, "l2": 0, "certified_flagged": []}
    for wid, v in data.items():
        w = db.session.get(Word, int(wid))
        if w is None: continue
        if w.certified:
            n["certified_flagged"].append(w.ref); continue
        if v["l1"] and (w.root_gloss or "") != v["l1"]:
            db.session.add(GlossRevision(word_id=w.id, editor_id=admin.id,
                old_gloss=f"[shoresh] {w.root_gloss or ''}", new_gloss=f"[shoresh] {v['l1']}"))
            w.root_gloss = v["l1"]; n["l1"] += 1
        if v["l2"] and (w.translation or "") != v["l2"]:
            db.session.add(GlossRevision(word_id=w.id, editor_id=admin.id,
                old_gloss=w.translation or "", new_gloss=v["l2"]))
            w.translation = v["l2"]; n["l2"] += 1
    db.session.commit()
    print("SEED MAGIL WINS:", json.dumps(n, ensure_ascii=False))
