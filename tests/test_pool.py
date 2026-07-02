"""The drill-pool rules are load-bearing: reveal IS the flag, marks are
computed server-side, graduation needs fast-correct on two different days."""

from datetime import datetime, timedelta, timezone

from app.services import pool

T0 = datetime(2026, 7, 2, 15, 0, tzinfo=timezone.utc)
DAY = timedelta(days=1)


def test_reveal_enters_pool_and_marks_miss(seeded):
    s = seeded
    att, state = pool.record_attempt(
        s["learner"].id, s["words"][0].id, s["session"].id,
        revealed=True, now=T0)
    assert att.mark == "miss"
    assert state.in_pool
    assert state.due_at == T0  # retry this same session


def test_fast_correct_is_know_slow_correct_is_hesitate(app, seeded):
    s = seeded
    assert pool.compute_mark(False, True, 1500) == "know"
    assert pool.compute_mark(False, True, 4001) == "hesitate"
    assert pool.compute_mark(False, False, 1000) == "miss"
    assert pool.compute_mark(True, True, 1000) == "miss"  # revealed => miss


def test_client_cannot_send_a_mark(client, seeded):
    s = seeded
    resp = client.post(f"/api/learners/{s['learner'].id}/attempts", json={
        "word_id": s["words"][0].id, "session_id": s["session"].id,
        "correct": True, "response_ms": 9000, "mark": "know",  # ignored
    })
    assert resp.get_json()["mark"] == "hesitate"


def test_graduation_requires_two_different_days(seeded):
    s = seeded
    lid, wid, sid = s["learner"].id, s["words"][0].id, s["session"].id
    pool.record_attempt(lid, wid, sid, revealed=True, now=T0)

    # Two fast corrects the SAME day: still in the pool.
    _, state = pool.record_attempt(lid, wid, sid, correct=True,
                                   response_ms=1000, now=T0 + timedelta(minutes=1))
    _, state = pool.record_attempt(lid, wid, sid, correct=True,
                                   response_ms=1000, now=T0 + timedelta(minutes=5))
    assert state.in_pool
    assert state.know_streak == 1

    # Fast correct the NEXT day: graduates.
    _, state = pool.record_attempt(lid, wid, sid, correct=True,
                                   response_ms=1000, now=T0 + DAY)
    assert not state.in_pool
    assert state.graduated_at is not None


def test_miss_resets_the_streak(seeded):
    s = seeded
    lid, wid, sid = s["learner"].id, s["words"][1].id, s["session"].id
    pool.record_attempt(lid, wid, sid, revealed=True, now=T0)
    pool.record_attempt(lid, wid, sid, correct=True, response_ms=1000, now=T0)
    _, state = pool.record_attempt(lid, wid, sid, correct=False, now=T0 + DAY)
    assert state.know_streak == 0
    assert state.in_pool
    # Fast correct after the miss starts the two-day count over.
    _, state = pool.record_attempt(lid, wid, sid, correct=True,
                                   response_ms=900, now=T0 + 2 * DAY)
    assert state.in_pool
    assert state.know_streak == 1


def test_retry_ladder_same_session_then_1_3_7_days(seeded):
    s = seeded
    lid, wid, sid = s["learner"].id, s["words"][2].id, s["session"].id
    _, state = pool.record_attempt(lid, wid, sid, revealed=True, now=T0)
    assert state.due_at == T0
    _, state = pool.record_attempt(lid, wid, sid, correct=False, now=T0)
    assert state.due_at == T0 + 1 * DAY
    _, state = pool.record_attempt(lid, wid, sid, correct=False, now=T0 + DAY)
    assert state.due_at == T0 + DAY + 3 * DAY
    _, state = pool.record_attempt(lid, wid, sid, correct=False, now=T0 + 4 * DAY)
    assert state.due_at == T0 + 4 * DAY + 7 * DAY
    # The ladder caps at 7 days.
    _, state = pool.record_attempt(lid, wid, sid, correct=False, now=T0 + 11 * DAY)
    assert state.due_at == T0 + 11 * DAY + 7 * DAY


def test_hesitate_keeps_word_in_pool(seeded):
    s = seeded
    lid, wid, sid = s["learner"].id, s["words"][3].id, s["session"].id
    pool.record_attempt(lid, wid, sid, revealed=True, now=T0)
    pool.record_attempt(lid, wid, sid, correct=True, response_ms=1000, now=T0)
    # Slow correct on day two: does NOT graduate.
    _, state = pool.record_attempt(lid, wid, sid, correct=True,
                                   response_ms=6000, now=T0 + DAY)
    assert state.in_pool
    assert state.know_streak == 0
