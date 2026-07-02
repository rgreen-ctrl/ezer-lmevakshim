"""The 10-Minute Seder: time is fixed, content flexes.

A lesson is ~18-30 new words (~2 pesukim), auto-sized, and ALWAYS ends at a
pasuk boundary. Drill decks mix 40% new / 40% weak / 20% maintenance.
"""

import random

from flask import current_app

from app import db
from app.models import Attempt, Word
from app.services.frontier import servable_pasuk_indexes
from app.services.pool import due_pool_words, graduated_states


def seen_word_ids(learner_id, unit_id=None):
    q = (
        db.session.query(Attempt.word_id)
        .filter(Attempt.learner_id == learner_id)
        .distinct()
    )
    if unit_id is not None:
        q = q.join(Word, Word.id == Attempt.word_id).filter(Word.unit_id == unit_id)
    return {row[0] for row in q}


def next_lesson_words(learner_id, unit_id):
    """New ground: the next unseen servable words, whole pesukim, sized to
    the 18-30 word window (never splitting a pasuk; a single long pasuk may
    exceed the max on its own). A pasuk is servable only when EVERY word in
    it is certified — the certified frontier."""
    lo = current_app.config["LESSON_MIN_NEW_WORDS"]
    hi = current_app.config["LESSON_MAX_NEW_WORDS"]
    seen = seen_word_ids(learner_id, unit_id)
    servable = servable_pasuk_indexes(unit_id)

    words = (
        Word.query.filter_by(unit_id=unit_id, certified=True)
        .order_by(Word.position)
        .all()
    )
    unseen = [w for w in words
              if w.id not in seen and w.pasuk_index in servable]
    if not unseen:
        return []

    lesson = []
    current_pasuk = None
    for w in unseen:
        if w.pasuk_index != current_pasuk:
            # At a pasuk boundary: stop if the window is satisfied, or if
            # adding another pasuk would overshoot while we already meet the
            # minimum.
            if lesson and len(lesson) >= lo:
                break
            current_pasuk = w.pasuk_index
        lesson.append(w)
        if len(lesson) >= hi and w.pasuk_index != current_pasuk:
            break
    return lesson


def build_drill_deck(learner_id, unit_id, size=20, now=None, rng=None):
    """Deal a drill deck: 40% new / 40% weak-pool / 20% maintenance.

    Shortfall in any bucket is filled from the weak pool first, then new,
    so a session is never padded with uncertified or foreign words.
    """
    rng = rng or random
    new_share, weak_share, maint_share = current_app.config["DRILL_MIX"]

    weak_states = due_pool_words(learner_id, now)
    weak_words = [s.word for s in weak_states if s.word.certified]

    seen = seen_word_ids(learner_id)
    servable = servable_pasuk_indexes(unit_id)
    new_words = (
        Word.query.filter_by(unit_id=unit_id, certified=True)
        .order_by(Word.position)
        .all()
    )
    new_words = [w for w in new_words
                 if w.id not in seen and w.pasuk_index in servable]

    maint_words = [
        s.word
        for s in graduated_states(learner_id)
        if s.word.certified and s.word.unit_id == unit_id
    ]

    deck = []
    deck += rng.sample(weak_words, min(len(weak_words), round(size * weak_share)))
    deck += new_words[: round(size * new_share)]
    if maint_words:
        deck += rng.sample(maint_words, min(len(maint_words), round(size * maint_share)))

    # Fill any shortfall: weak pool first, then new ground.
    have = {w.id for w in deck}
    for w in weak_words + new_words:
        if len(deck) >= size:
            break
        if w.id not in have:
            deck.append(w)
            have.add(w.id)

    rng.shuffle(deck)
    return deck[:size]
