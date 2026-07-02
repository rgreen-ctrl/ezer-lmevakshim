"""Reveal-driven drill pool.

The rules (locked — see CLAUDE.md):
- Revealing a word's translation IS the flag: it enters the pool. No undo.
- Marks are computed server-side: revealed => miss; correct under the
  hesitation threshold => know; correct but slow => hesitate; wrong => miss.
- Pool lifecycle on a non-graduating answer: retry same session -> next day
  -> 3 days -> 7 days.
- Graduation (pool exit) = fast-correct in two sessions on DIFFERENT days.
"""

from datetime import datetime, timedelta, timezone

from flask import current_app

from app import db
from app.models import Attempt, WordState


def utcnow():
    return datetime.now(timezone.utc)


def _get_state(learner_id, word_id):
    state = WordState.query.filter_by(learner_id=learner_id, word_id=word_id).first()
    if state is None:
        state = WordState(learner_id=learner_id, word_id=word_id)
        db.session.add(state)
    return state


def compute_mark(revealed, correct, response_ms):
    """Server-side mark. The client reports only what happened, never the mark."""
    if revealed or not correct:
        return "miss"
    if response_ms is None or response_ms > current_app.config["HESITATION_MS"]:
        return "hesitate"
    return "know"


def enter_pool(state, now=None):
    now = now or utcnow()
    if not state.in_pool:
        state.in_pool = True
        state.pool_entered_at = now
        state.interval_step = 0
        state.know_streak = 0
        state.graduated_at = None
    state.due_at = now  # retry this same session
    return state


def _reschedule(state, now):
    """Advance the retry ladder: same session -> +1d -> +3d -> +7d."""
    intervals = current_app.config["POOL_INTERVALS_DAYS"]
    state.interval_step = min(state.interval_step + 1, len(intervals) - 1)
    state.due_at = now + timedelta(days=intervals[state.interval_step])


def record_attempt(learner_id, word_id, session_id, *, revealed=False,
                   correct=False, response_ms=None, source="self", now=None):
    """Record one answer and update pool state. Returns (attempt, state).

    Self-marks can graduate a word out of the drill pool (that is the pool's
    own rule) but NEVER promote a rung — promotion happens only in
    services/promotion.py from verified tests.
    """
    now = now or utcnow()
    mark = compute_mark(revealed, correct, response_ms)

    attempt = Attempt(
        learner_id=learner_id,
        word_id=word_id,
        session_id=session_id,
        mark=mark,
        source=source,
        revealed=revealed,
        response_ms=response_ms,
        created_at=now,
    )
    db.session.add(attempt)

    state = _get_state(learner_id, word_id)

    if revealed or mark == "miss" or mark == "hesitate":
        # Any reveal, wrong answer, or slow answer puts/keeps the word in the
        # pool and resets the graduation streak.
        enter_pool(state, now)
        if not revealed:
            state.know_streak = 0
            _reschedule(state, now)
    elif state.in_pool:
        # Fast correct while in the pool: count toward graduation.
        today = now.date()
        if state.last_fast_correct_on == today:
            # Same-day repeat: keeps the word alive but two-different-days
            # rule means it cannot graduate today.
            _reschedule(state, now)
        else:
            state.know_streak += 1
            state.last_fast_correct_on = today
            if state.know_streak >= 2:
                state.in_pool = False
                state.graduated_at = now
                state.due_at = None
            else:
                _reschedule(state, now)

    db.session.flush()
    return attempt, state


def due_pool_words(learner_id, now=None):
    """Weak-pool words currently due for this learner."""
    now = now or utcnow()
    return (
        WordState.query.filter_by(learner_id=learner_id, in_pool=True)
        .filter(WordState.due_at <= now)
        .order_by(WordState.due_at)
        .all()
    )


def graduated_states(learner_id):
    return WordState.query.filter_by(learner_id=learner_id, in_pool=False).filter(
        WordState.graduated_at.isnot(None)
    )
