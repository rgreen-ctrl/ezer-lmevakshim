"""The Certification Desk — the only place certification happens.

Every route under /desk is gated by a blueprint-level before_request: no
staff session (learner or anonymous alike) means 403, checked server-side.
The editor walks the parsha pasuk by pasuk in the same interlinear layout
the learner will get, corrects what needs correcting, and approves word by
word — or one whole pasuk at a time, never more.
"""

from flask import Blueprint, g, jsonify, request

from app import db
from app.auth import require_staff
from app.models import GlossRevision, Track, Unit, Word, WordFlag
from app.services import certify
from app.services.frontier import servable_pasuk_indexes, unit_progress

desk = Blueprint("desk", __name__)


@desk.before_request
def _gate():
    require_staff()


@desk.errorhandler(ValueError)
def _value_error(e):
    return jsonify({"error": str(e)}), 400


@desk.errorhandler(PermissionError)
def _permission_error(e):
    return jsonify({"error": str(e)}), 403


def _word_json(w, open_flags=None):
    return {
        "id": w.id,
        "ref": w.ref,
        "pasuk_index": w.pasuk_index,
        "position": w.position,
        "hebrew": w.hebrew,
        "gloss": w.translation,
        "shoresh": w.shoresh,
        "certified": w.certified,
        "open_flags": open_flags.get(w.id, 0) if open_flags else 0,
    }


def _open_flag_counts(word_ids):
    rows = (
        db.session.query(WordFlag.word_id, db.func.count(WordFlag.id))
        .filter(WordFlag.word_id.in_(word_ids), WordFlag.status == "open")
        .group_by(WordFlag.word_id)
        .all()
    )
    return dict(rows)


# --- Overview ----------------------------------------------------------------

@desk.get("/")
def home():
    tracks = Track.query.order_by(Track.rung_order).all()
    out = []
    for t in tracks:
        units = [{"id": u.id, "name": u.name, "kind": u.kind,
                  **unit_progress(u.id)} for u in t.units]
        out.append({"id": t.id, "key": t.key, "name": t.name, "units": units})
    open_flags = WordFlag.query.filter_by(status="open").count()
    return jsonify({
        "desk": "The Certification Desk",
        "staff": {"name": g.staff.name, "role": g.staff.role},
        "tracks": out,
        "open_flags": open_flags,
    })


@desk.get("/units/<int:unit_id>")
def unit_view(unit_id):
    unit = db.get_or_404(Unit, unit_id)
    words = Word.query.filter_by(unit_id=unit_id).order_by(Word.position).all()
    pesukim = {}
    for w in words:
        p = pesukim.setdefault(w.pasuk_index, {
            "pasuk_index": w.pasuk_index, "ref": w.ref,
            "words_total": 0, "words_certified": 0})
        p["words_total"] += 1
        p["words_certified"] += 1 if w.certified else 0
    return jsonify({
        "unit": {"id": unit.id, "name": unit.name, "kind": unit.kind},
        "progress": unit_progress(unit_id),
        "pesukim": [pesukim[k] for k in sorted(pesukim)],
    })


@desk.get("/units/<int:unit_id>/pasuk/<int:pasuk_index>")
def pasuk_view(unit_id, pasuk_index):
    """The interlinear review view: the pasuk exactly as the learner will
    eventually see it — Hebrew with its gloss underneath, in order."""
    words = (
        Word.query.filter_by(unit_id=unit_id, pasuk_index=pasuk_index)
        .order_by(Word.position)
        .all()
    )
    if not words:
        return jsonify({"error": "no such pasuk"}), 404
    flags = _open_flag_counts([w.id for w in words])
    return jsonify({
        "ref": words[0].ref,
        "pasuk_index": pasuk_index,
        "servable": pasuk_index in servable_pasuk_indexes(unit_id),
        "words": [_word_json(w, flags) for w in words],
    })


# --- Word actions ------------------------------------------------------------

@desk.post("/words/<int:word_id>/approve")
def approve(word_id):
    word = db.get_or_404(Word, word_id)
    certify.approve_word(word, g.staff)
    db.session.commit()
    return jsonify({"certified": True,
                    "pasuk_servable": word.pasuk_index
                    in servable_pasuk_indexes(word.unit_id)})


@desk.post("/words/<int:word_id>/gloss")
def gloss(word_id):
    word = db.get_or_404(Word, word_id)
    data = request.get_json(force=True)
    revision = certify.edit_gloss(word, g.staff, data.get("new_gloss"))
    db.session.commit()
    return jsonify({"gloss": word.translation,
                    "certified": word.certified,
                    "revision_id": revision.id if revision else None})


@desk.post("/words/<int:word_id>/flag")
def flag(word_id):
    word = db.get_or_404(Word, word_id)
    data = request.get_json(force=True)
    f = certify.raise_flag(word, g.staff, data.get("note"))
    db.session.commit()
    return jsonify({"flag_id": f.id}), 201


@desk.post("/words/<int:word_id>/decertify")
def decertify(word_id):
    word = db.get_or_404(Word, word_id)
    data = request.get_json(force=True)
    f = certify.decertify_word(word, g.staff, data.get("reason"))
    db.session.commit()
    return jsonify({"certified": False, "flag_id": f.id})


@desk.post("/units/<int:unit_id>/pasuk/<int:pasuk_index>/certify")
def certify_pasuk(unit_id, pasuk_index):
    """The only bulk approval — deliberately pasuk-sized, the granularity a
    person actually just read. There is no certify-aliyah or certify-parsha."""
    exists = Word.query.filter_by(unit_id=unit_id,
                                  pasuk_index=pasuk_index).first()
    if exists is None:
        return jsonify({"error": "no such pasuk"}), 404
    n = certify.certify_pasuk(unit_id, pasuk_index, g.staff)
    db.session.commit()
    return jsonify({"certified_now": n,
                    "pasuk_servable": pasuk_index
                    in servable_pasuk_indexes(unit_id)})


# --- Flag queue --------------------------------------------------------------

@desk.get("/flags")
def flags():
    open_flags = (
        WordFlag.query.filter_by(status="open")
        .order_by(WordFlag.created_at)
        .all()
    )
    out = []
    for f in open_flags:
        context = (
            Word.query.filter_by(unit_id=f.word.unit_id,
                                 pasuk_index=f.word.pasuk_index)
            .order_by(Word.position)
            .all()
        )
        out.append({
            "id": f.id,
            "word": _word_json(f.word),
            "note": f.note,
            "raised_by_kind": f.raised_by_kind,
            "created_at": f.created_at.isoformat(),
            "pasuk": [{"hebrew": w.hebrew, "gloss": w.translation}
                      for w in context],
        })
    return jsonify({"flags": out})


@desk.post("/flags/<int:flag_id>/resolve")
def resolve(flag_id):
    f = db.get_or_404(WordFlag, flag_id)
    data = request.get_json(force=True)
    certify.resolve_flag(f, g.staff,
                         new_gloss=data.get("new_gloss"),
                         note=data.get("note"))
    db.session.commit()
    return jsonify({"status": f.status,
                    "word": _word_json(f.word)})


# --- Audit -------------------------------------------------------------------

@desk.get("/words/<int:word_id>/revisions")
def revisions(word_id):
    db.get_or_404(Word, word_id)
    rows = (
        GlossRevision.query.filter_by(word_id=word_id)
        .order_by(GlossRevision.created_at)
        .all()
    )
    return jsonify({"revisions": [{
        "old_gloss": r.old_gloss, "new_gloss": r.new_gloss,
        "editor": r.editor.name, "created_at": r.created_at.isoformat(),
    } for r in rows]})
