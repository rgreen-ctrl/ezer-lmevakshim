"""Verified tests and rung promotion.

The gate (locked — see CLAUDE.md): promotion happens ONLY through an
in-person verified test — the app deals 25 random certified words from the
rung, a human tester marks each Pass / Hesitated / Fail — and passes ONLY
with zero fails and zero hesitations. Self-marks never promote.
"""

import random

from flask import current_app

from app import db
from app.models import Attempt, Learner, Promotion, Session, Track, Unit, Word
from app.services.pool import utcnow

TESTER_MARKS = {"pass", "hesitate", "fail"}


def deal_verified_test(learner_id, track_id, tester_name, rng=None):
    """Start a verified test: open a session and deal random certified words
    drawn across the whole rung."""
    rng = rng or random
    size = current_app.config["VERIFIED_TEST_SIZE"]

    words = (
        Word.query.join(Unit, Word.unit_id == Unit.id)
        .filter(Unit.track_id == track_id, Word.certified.is_(True))
        .all()
    )
    if len(words) < size:
        raise ValueError(
            f"Track has only {len(words)} certified words; {size} required."
        )

    session = Session(learner_id=learner_id, mode="verified")
    db.session.add(session)
    db.session.flush()

    dealt = rng.sample(words, size)
    return session, dealt


def record_tester_mark(learner_id, word_id, session_id, tester_mark):
    """A tester's oral mark. This is the only place a client-supplied mark is
    accepted, and it is stored as source='verified'."""
    if tester_mark not in TESTER_MARKS:
        raise ValueError(f"Unknown tester mark: {tester_mark}")

    session = db.session.get(Session, session_id)
    if session is None or session.mode != "verified":
        raise ValueError("Tester marks are only accepted inside a verified test.")

    mark = {"pass": "know", "hesitate": "hesitate", "fail": "miss"}[tester_mark]
    attempt = Attempt(
        learner_id=learner_id,
        word_id=word_id,
        session_id=session_id,
        mark=mark,
        source="verified",
        revealed=False,
        response_ms=None,
        created_at=utcnow(),
    )
    db.session.add(attempt)
    db.session.flush()
    return attempt


def complete_verified_test(learner_id, track_id, session_id, tester_name):
    """Score the test and promote if — and only if — zero fails and zero
    hesitations across every dealt word."""
    session = db.session.get(Session, session_id)
    if session is None or session.mode != "verified":
        raise ValueError("Not a verified-test session.")

    attempts = Attempt.query.filter_by(
        session_id=session_id, learner_id=learner_id, source="verified"
    ).all()
    if not attempts:
        raise ValueError("No tester marks recorded for this test.")

    fails = sum(1 for a in attempts if a.mark == "miss")
    hesitations = sum(1 for a in attempts if a.mark == "hesitate")
    passed = fails == 0 and hesitations == 0

    promotion = Promotion(
        learner_id=learner_id,
        track_id=track_id,
        session_id=session_id,
        tester_name=tester_name,
        words_dealt=len(attempts),
        fails=fails,
        hesitations=hesitations,
        passed=passed,
    )
    db.session.add(promotion)

    if passed:
        learner = db.session.get(Learner, learner_id)
        track = db.session.get(Track, track_id)
        # Rungs unlock strictly in order — passing a lower rung never skips.
        if track.rung_order == learner.current_rung:
            learner.current_rung += 1

    session.ended_at = utcnow()
    db.session.flush()
    return promotion


def ladder_for(learner):
    """The learner's ladder view: each rung with its locked/current/done state."""
    tracks = Track.query.order_by(Track.rung_order).all()
    out = []
    for t in tracks:
        if t.rung_order < learner.current_rung:
            status = "completed"
        elif t.rung_order == learner.current_rung:
            status = "current"
        else:
            status = "locked"
        out.append({"id": t.id, "key": t.key, "name": t.name,
                    "rung": t.rung_order, "status": status})
    return out
