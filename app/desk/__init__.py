"""The Certification Desk — the only place certification happens.

Every route under /desk is gated by a blueprint-level before_request: no
staff session (learner or anonymous alike) means 403, checked server-side.
The editor walks the parsha pasuk by pasuk in the same interlinear layout
the learner will get, corrects what needs correcting, and approves word by
word — or one whole pasuk at a time, never more.
"""

import json

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


@desk.errorhandler(403)
def _forbidden(e):
    # The staff gate uses abort(403); return JSON (not Flask's HTML page) so the
    # Desk can tell an ended session apart from real data and prompt re-login,
    # instead of silently swallowing an HTML body into an empty view.
    return jsonify({"error": "Staff sign-in required — your session may have ended."}), 403


def _word_json(w, open_flags=None):
    return {
        "id": w.id,
        "ref": w.ref,
        "pasuk_index": w.pasuk_index,
        "position": w.position,
        "hebrew": w.hebrew,
        "gloss": w.translation,
        "shoresh": w.shoresh,
        "root_gloss": w.root_gloss,
        "contextual": w.contextual_translation,
        "contextual_flagged": w.contextual_flagged,
        "contextual_note": w.contextual_note,
        "suggestions": json.loads(w.suggestions) if w.suggestions else [],
        "confidence": w.confidence,
        "check_results": json.loads(w.check_results) if w.check_results else [],
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


@desk.get("/units/<int:unit_id>/queue")
def review_queue(unit_id):
    """Prioritized review order: LOW-confidence words first, then MEDIUM, then
    HIGH — so the editor spends time where judgment is needed. Confidence only
    ORDERS; it never approves. Nothing here certifies."""
    db.get_or_404(Unit, unit_id)
    words = Word.query.filter_by(unit_id=unit_id).all()
    rank = {"low": 0, "medium": 1, "high": 2}
    words.sort(key=lambda w: (rank.get(w.confidence, 3), w.pasuk_index, w.position))
    counts = {lvl: sum(1 for w in words if w.confidence == lvl)
              for lvl in ("low", "medium", "high")}
    return jsonify({
        "counts": counts,
        "words": [{
            "id": w.id, "ref": w.ref, "pasuk_index": w.pasuk_index,
            "position": w.position, "hebrew": w.hebrew,
            "confidence": w.confidence, "certified": w.certified,
            "reasons": [r.get("reason") for r in
                        (json.loads(w.check_results) if w.check_results else [])],
        } for w in words],
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


@desk.post("/words/<int:word_id>/contextual")
def contextual(word_id):
    """Edit the DRAFT contextual translation (what the learner will eventually
    read). Editing it clears its review flag. This never touches the literal
    gloss or the certified state — certification is still the pasuk action."""
    word = db.get_or_404(Word, word_id)
    data = request.get_json(force=True)
    val = (data.get("contextual_translation") or "").strip()
    word.contextual_translation = val or None
    word.contextual_flagged = False
    db.session.commit()
    return jsonify({"contextual_translation": word.contextual_translation,
                    "contextual_flagged": word.contextual_flagged})


@desk.post("/words/<int:word_id>/root")
def root_gloss(word_id):
    """Edit the DRAFT Layer-1 root meaning (shoresh).

    scope='one' (default): this word only. scope='root': every word sharing
    this Hebrew shoresh — global is NEVER the default; the editor chooses each
    time. Certified words are never touched by a global pass: they are
    reported back for the editor to reopen deliberately. Every change writes a
    GlossRevision row (audit; rows are never deleted). Layer 2 has no global —
    the same root inflects differently, so a global literal is usually wrong."""
    word = db.get_or_404(Word, word_id)
    data = request.get_json(force=True)
    val = (data.get("root_gloss") or "").strip() or None
    scope = data.get("scope", "one")
    changed, skipped_certified = [], []
    targets = [word]
    siblings = []
    if word.shoresh:
        siblings = (Word.query.filter(Word.shoresh == word.shoresh,
                                      Word.id != word.id).all())
    if scope == "root":
        targets += siblings
    for w in targets:
        if w.certified and w.id != word.id:
            skipped_certified.append(w.ref)
            continue
        if (w.root_gloss or None) != val:
            db.session.add(GlossRevision(
                word_id=w.id, editor_id=g.staff.id,
                old_gloss=f"[shoresh] {w.root_gloss or ''}",
                new_gloss=f"[shoresh] {val or ''}"))
            w.root_gloss = val
            changed.append(w.id)
    db.session.commit()
    return jsonify({
        "root_gloss": word.root_gloss,
        "scope": scope,
        "changed": len(changed),
        "same_root_others": len(siblings),
        "certified_skipped": skipped_certified,   # reopen these deliberately
    })


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
