import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app, db
from app.models import Learner, Session, Track, Unit, Word

# CI runs the same suite twice: SQLite (default) and Postgres (service
# container, via TEST_DATABASE_URL) — migrations must run clean on both.
TEST_DB = os.environ.get("TEST_DATABASE_URL", "sqlite:///:memory:")


@pytest.fixture()
def app():
    app = create_app({
        "SQLALCHEMY_DATABASE_URI": TEST_DB,
        "TESTING": True,
    })
    with app.app_context():
        db.create_all()
        yield app
        db.session.rollback()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def seeded(app):
    """A learner, the chumash track, one unit, and 30 certified words plus
    one uncertified word."""
    track = Track(key="chumash", name="Chumash", rung_order=1)
    db.session.add(track)
    db.session.flush()
    unit = Unit(track_id=track.id, kind="parsha", name="Noach", order_index=1)
    db.session.add(unit)
    db.session.flush()
    words = []
    for i in range(1, 31):
        w = Word(unit_id=unit.id, ref=f"Bereishis 6:{9 + (i - 1) // 10}",
                 pasuk_index=1 + (i - 1) // 10, position=i,
                 hebrew=f"מלה{i}", translation=f"word {i}", certified=True)
        db.session.add(w)
        words.append(w)
    uncertified = Word(unit_id=unit.id, ref="Bereishis 6:12", pasuk_index=4,
                       position=99, hebrew="חול", translation="uncertified",
                       certified=False)
    db.session.add(uncertified)
    learner = Learner(first_name="Dovid", last_name="Green",
                      cell="555-0100", email="dovid@example.org")
    db.session.add(learner)
    db.session.flush()
    session = Session(learner_id=learner.id, unit_id=unit.id, mode="drill")
    db.session.add(session)
    db.session.commit()
    return {"track": track, "unit": unit, "words": words,
            "uncertified": uncertified, "learner": learner, "session": session}
