from flask import Blueprint, jsonify, request

from app import db
from app.models import Learner, Session, Track, Unit, Word
from app.services import lessons, pool, promotion

api = Blueprint("api", __name__)


def word_json(w, include_translation=False):
    out = {"id": w.id, "ref": w.ref, "hebrew": w.hebrew, "position": w.position,
           "pasuk_index": w.pasuk_index}
    if include_translation:
        out["translation"] = w.translation
    return out


@api.errorhandler(ValueError)
def value_error(e):
    return jsonify({"error": str(e)}), 400


# --- Registration & ladder -------------------------------------------------

@api.post("/register")
def register():
    data = request.get_json(force=True)
    for field in ("first_name", "last_name", "cell", "email"):
        if not data.get(field, "").strip():
            return jsonify({"error": f"{field} is required"}), 400
    if Learner.query.filter_by(email=data["email"].strip().lower()).first():
        return jsonify({"error": "email already registered"}), 409
    learner = Learner(
        first_name=data["first_name"].strip(),
        last_name=data["last_name"].strip(),
        cell=data["cell"].strip(),
        email=data["email"].strip().lower(),
    )
    db.session.add(learner)
    db.session.commit()
    return jsonify({"learner_id": learner.id}), 201


@api.post("/signin")
def signin():
    data = request.get_json(force=True)
    learner = Learner.query.filter_by(
        email=data.get("email", "").strip().lower()
    ).first()
    if learner is None:
        return jsonify({"error": "not registered"}), 404
    return jsonify({"learner_id": learner.id,
                    "first_name": learner.first_name,
                    "current_rung": learner.current_rung})


@api.get("/learners/<int:learner_id>/ladder")
def ladder(learner_id):
    learner = db.get_or_404(Learner, learner_id)
    return jsonify({"current_rung": learner.current_rung,
                    "ladder": promotion.ladder_for(learner)})


# --- Learn mode -------------------------------------------------------------

@api.get("/learners/<int:learner_id>/units")
def units(learner_id):
    learner = db.get_or_404(Learner, learner_id)
    track = Track.query.filter_by(rung_order=learner.current_rung).first()
    if track is None:
        return jsonify({"units": []})
    return jsonify({
        "track": {"id": track.id, "name": track.name},
        "units": [{"id": u.id, "name": u.name, "kind": u.kind}
                  for u in track.units],
    })


@api.post("/learners/<int:learner_id>/sessions")
def start_session(learner_id):
    db.get_or_404(Learner, learner_id)
    data = request.get_json(force=True)
    mode = data.get("mode")
    if mode not in ("learn", "drill"):
        return jsonify({"error": "mode must be learn or drill"}), 400
    session = Session(learner_id=learner_id, mode=mode,
                      unit_id=data.get("unit_id"))
    db.session.add(session)
    db.session.commit()
    return jsonify({"session_id": session.id}), 201


@api.get("/learners/<int:learner_id>/lesson")
def lesson(learner_id):
    db.get_or_404(Learner, learner_id)
    unit_id = request.args.get("unit_id", type=int)
    if not unit_id:
        return jsonify({"error": "unit_id required"}), 400
    words = lessons.next_lesson_words(learner_id, unit_id)
    # Learn mode shows the parsha in order; translations come only through
    # the reveal endpoint so that every reveal is recorded.
    return jsonify({"words": [word_json(w) for w in words]})


@api.post("/learners/<int:learner_id>/reveal")
def reveal(learner_id):
    """Tap-to-reveal in Learn mode. Revealing IS the flag — the word enters
    the drill pool automatically. No undo."""
    db.get_or_404(Learner, learner_id)
    data = request.get_json(force=True)
    word = db.get_or_404(Word, int(data["word_id"]))
    if not word.certified:
        return jsonify({"error": "word not certified"}), 403
    pool.record_attempt(
        learner_id, word.id, int(data["session_id"]),
        revealed=True, correct=False, response_ms=data.get("response_ms"),
    )
    db.session.commit()
    return jsonify({"translation": word.translation})


# --- Drill mode -------------------------------------------------------------

@api.get("/learners/<int:learner_id>/drill")
def drill(learner_id):
    db.get_or_404(Learner, learner_id)
    unit_id = request.args.get("unit_id", type=int)
    size = request.args.get("size", default=20, type=int)
    if not unit_id:
        return jsonify({"error": "unit_id required"}), 400
    deck = lessons.build_drill_deck(learner_id, unit_id, size=size)
    return jsonify({"words": [word_json(w) for w in deck]})


@api.post("/learners/<int:learner_id>/attempts")
def attempt(learner_id):
    """Claim-then-confirm drill answer. The client reports what happened
    (claimed, confirmed correct, response time); the mark is computed here."""
    db.get_or_404(Learner, learner_id)
    data = request.get_json(force=True)
    word = db.get_or_404(Word, int(data["word_id"]))
    if not word.certified:
        return jsonify({"error": "word not certified"}), 403
    att, state = pool.record_attempt(
        learner_id, word.id, int(data["session_id"]),
        revealed=bool(data.get("revealed", False)),
        correct=bool(data.get("correct", False)),
        response_ms=data.get("response_ms"),
    )
    db.session.commit()
    return jsonify({
        "mark": att.mark,
        "in_pool": state.in_pool,
        "know_streak": state.know_streak,
        "translation": word.translation,
    })


@api.get("/learners/<int:learner_id>/results")
def results(learner_id):
    """End-of-lesson view: this session's missed and hesitated words."""
    db.get_or_404(Learner, learner_id)
    session_id = request.args.get("session_id", type=int)
    from app.models import Attempt
    rows = Attempt.query.filter_by(learner_id=learner_id, session_id=session_id).all()
    weak = [a for a in rows if a.mark in ("miss", "hesitate")]
    return jsonify({
        "total": len(rows),
        "known": sum(1 for a in rows if a.mark == "know"),
        "weak": [dict(word_json(a.word, include_translation=True), mark=a.mark)
                 for a in weak],
    })


# --- Tester Mode (verified tests) --------------------------------------------

@api.post("/tester/tests")
def start_test():
    data = request.get_json(force=True)
    session, dealt = promotion.deal_verified_test(
        int(data["learner_id"]), int(data["track_id"]),
        data.get("tester_name", "").strip() or "unknown",
    )
    db.session.commit()
    return jsonify({
        "session_id": session.id,
        "words": [word_json(w, include_translation=True) for w in dealt],
    }), 201


@api.post("/tester/tests/<int:session_id>/mark")
def tester_mark(session_id):
    data = request.get_json(force=True)
    promotion.record_tester_mark(
        int(data["learner_id"]), int(data["word_id"]), session_id,
        data.get("mark"),
    )
    db.session.commit()
    return jsonify({"ok": True})


@api.post("/tester/tests/<int:session_id>/complete")
def complete_test(session_id):
    data = request.get_json(force=True)
    promo = promotion.complete_verified_test(
        int(data["learner_id"]), int(data["track_id"]), session_id,
        data.get("tester_name", "").strip() or "unknown",
    )
    db.session.commit()
    return jsonify({
        "passed": promo.passed,
        "fails": promo.fails,
        "hesitations": promo.hesitations,
        "words_dealt": promo.words_dealt,
    })
