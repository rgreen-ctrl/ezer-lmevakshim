"""The promotion gate is locked: verified tests only, zero fails AND zero
hesitations; self-marks never promote a rung."""

import pytest

from app import db
from app.services import pool, promotion


def _run_test(s, marks):
    session, dealt = promotion.deal_verified_test(
        s["learner"].id, s["track"].id, "R' Tester")
    for word, mark in zip(dealt, marks(dealt)):
        promotion.record_tester_mark(s["learner"].id, word.id, session.id, mark)
    return promotion.complete_verified_test(
        s["learner"].id, s["track"].id, session.id, "R' Tester")


def test_clean_test_promotes(seeded):
    s = seeded
    promo = _run_test(s, lambda dealt: ["pass"] * len(dealt))
    assert promo.passed
    assert s["learner"].current_rung == 2


def test_one_hesitation_fails_the_gate(seeded):
    s = seeded
    promo = _run_test(
        s, lambda dealt: ["hesitate"] + ["pass"] * (len(dealt) - 1))
    assert not promo.passed
    assert promo.hesitations == 1
    assert s["learner"].current_rung == 1


def test_one_fail_fails_the_gate(seeded):
    s = seeded
    promo = _run_test(s, lambda dealt: ["fail"] + ["pass"] * (len(dealt) - 1))
    assert not promo.passed
    assert s["learner"].current_rung == 1


def test_test_deals_25_words(app, seeded):
    s = seeded
    session, dealt = promotion.deal_verified_test(
        s["learner"].id, s["track"].id, "R' Tester")
    assert len(dealt) == app.config["VERIFIED_TEST_SIZE"]
    assert all(w.certified for w in dealt)


def test_self_marks_never_promote(seeded):
    """A learner can self-mark every word 'know' forever — the rung must not
    move without a verified test."""
    s = seeded
    for w in s["words"]:
        pool.record_attempt(s["learner"].id, w.id, s["session"].id,
                            correct=True, response_ms=800)
    db.session.commit()
    assert s["learner"].current_rung == 1


def test_tester_marks_rejected_outside_verified_session(seeded):
    s = seeded
    with pytest.raises(ValueError):
        promotion.record_tester_mark(
            s["learner"].id, s["words"][0].id, s["session"].id, "pass")


def test_not_enough_certified_words_refuses_to_deal(app, seeded):
    app.config["VERIFIED_TEST_SIZE"] = 100
    with pytest.raises(ValueError):
        promotion.deal_verified_test(
            seeded["learner"].id, seeded["track"].id, "R' Tester")
