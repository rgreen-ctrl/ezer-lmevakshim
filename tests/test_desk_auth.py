"""D1 gate tests: editors sign in with real credentials and reach /desk;
learners and anonymous requests get 403 on EVERY desk route, checked
server-side."""

import re

import pytest

from app import db
from app.auth import create_staff


@pytest.fixture()
def editor(app):
    staff = create_staff("R' Editor", "editor@example.org", "correct-horse", "editor")
    db.session.commit()
    return staff


@pytest.fixture()
def admin(app):
    staff = create_staff("R' Admin", "admin@example.org", "battery-staple", "admin")
    db.session.commit()
    return staff


def login(client, email, password):
    return client.post("/api/staff/login", json={"email": email,
                                                 "password": password})


def all_desk_routes(app):
    """Every route registered under /desk, with path params filled in —
    new D2 routes are swept automatically."""
    rules = [r for r in app.url_map.iter_rules() if r.rule.startswith("/desk")]
    assert rules, "no desk routes registered"
    return [(re.sub(r"<[^>]+>", "1", r.rule), r.methods - {"HEAD", "OPTIONS"})
            for r in rules]


def test_editor_signs_in_and_reaches_desk(client, editor):
    resp = login(client, "editor@example.org", "correct-horse")
    assert resp.status_code == 200
    assert resp.get_json()["role"] == "editor"

    resp = client.get("/desk/")
    assert resp.status_code == 200
    assert resp.get_json()["staff"]["name"] == "R' Editor"


def test_wrong_password_is_rejected(client, editor):
    assert login(client, "editor@example.org", "wrong").status_code == 401
    assert client.get("/desk/").status_code == 403


def test_logout_closes_the_desk(client, editor):
    login(client, "editor@example.org", "correct-horse")
    client.post("/api/staff/logout")
    assert client.get("/desk/").status_code == 403


def test_anonymous_gets_403_on_every_desk_route(app, client):
    for path, methods in all_desk_routes(app):
        for method in methods:
            resp = client.open(path, method=method)
            assert resp.status_code == 403, (path, method)


def test_learner_session_gets_403_on_every_desk_route(app, client, seeded):
    """A registered learner using the learner API holds no staff session —
    the desk must refuse them exactly like an anonymous request."""
    resp = client.post("/api/signin", json={"email": "dovid@example.org"})
    assert resp.status_code == 200  # learner is signed in on the learner side
    for path, methods in all_desk_routes(app):
        for method in methods:
            resp = client.open(path, method=method)
            assert resp.status_code == 403, (path, method)


def test_staff_me_requires_session(client, editor):
    assert client.get("/api/staff/me").status_code == 403
    login(client, "editor@example.org", "correct-horse")
    assert client.get("/api/staff/me").get_json()["role"] == "editor"


def test_create_staff_validations(app, editor):
    with pytest.raises(ValueError):
        create_staff("X", "editor@example.org", "long-enough", "editor")  # dup
    with pytest.raises(ValueError):
        create_staff("X", "new@example.org", "short", "editor")  # weak password
    with pytest.raises(ValueError):
        create_staff("X", "new@example.org", "long-enough", "boss")  # bad role


def test_schema_includes_audit_tables(app):
    """gloss_revisions, word_flags, and the certified_by/at columns exist on
    whichever backend the suite runs against (SQLite locally, Postgres in CI)."""
    from sqlalchemy import inspect

    insp = inspect(db.engine)
    tables = insp.get_table_names()
    assert "staff" in tables
    assert "gloss_revisions" in tables
    assert "word_flags" in tables
    word_cols = {c["name"] for c in insp.get_columns("words")}
    assert {"certified", "certified_by", "certified_at"} <= word_cols
