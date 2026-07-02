"""D2 gate tests: revisions on every edit, pasuk-granularity certification,
the exact-moment frontier rule, and no certification path from any learner
endpoint."""

import pytest

from app import db
from app.auth import create_staff
from app.models import GlossRevision, Word, WordFlag


@pytest.fixture()
def desk_setup(app, seeded):
    """Staff accounts plus the seeded unit flipped back to all-draft, the
    state a fresh corpus import leaves it in."""
    editor = create_staff("R' Editor", "editor@example.org", "correct-horse",
                          "editor")
    admin = create_staff("R' Admin", "admin@example.org", "battery-staple",
                         "admin")
    for w in seeded["words"]:
        w.certified = False
    db.session.commit()
    return {**seeded, "editor": editor, "admin": admin}


def as_editor(client):
    client.post("/api/staff/login", json={"email": "editor@example.org",
                                          "password": "correct-horse"})
    return client


def as_admin(client):
    client.post("/api/staff/login", json={"email": "admin@example.org",
                                          "password": "battery-staple"})
    return client


# --- Editing and the audit trail ---------------------------------------------

def test_edit_gloss_writes_revision_row(client, desk_setup):
    s = desk_setup
    w = s["words"][0]
    resp = as_editor(client).post(f"/desk/words/{w.id}/gloss",
                                  json={"new_gloss": "these are"})
    assert resp.status_code == 200
    assert resp.get_json()["gloss"] == "these are"
    rev = GlossRevision.query.filter_by(word_id=w.id).one()
    assert rev.old_gloss == "word 1"
    assert rev.new_gloss == "these are"
    assert rev.editor_id == s["editor"].id


def test_noop_edit_writes_no_revision(client, desk_setup):
    w = desk_setup["words"][0]
    as_editor(client).post(f"/desk/words/{w.id}/gloss",
                           json={"new_gloss": w.translation})
    assert GlossRevision.query.count() == 0


def test_editing_certified_word_stays_certified(client, desk_setup):
    s = desk_setup
    w = s["words"][0]
    c = as_editor(client)
    c.post(f"/desk/words/{w.id}/approve")
    resp = c.post(f"/desk/words/{w.id}/gloss", json={"new_gloss": "corrected"})
    assert resp.get_json()["certified"] is True
    assert GlossRevision.query.filter_by(word_id=w.id).count() == 1
    assert db.session.get(Word, w.id).certified


# --- Certification and the frontier ------------------------------------------

def test_approve_word_records_who_and_when(client, desk_setup):
    s = desk_setup
    w = s["words"][0]
    as_editor(client).post(f"/desk/words/{w.id}/approve")
    w = db.session.get(Word, w.id)
    assert w.certified
    assert w.certified_by == s["editor"].id
    assert w.certified_at is not None


def test_pasuk_serves_at_the_exact_moment_last_word_certifies(client, desk_setup):
    """The core D2 gate: word-by-word certification of pasuk 1; the learner
    lesson stays empty until the LAST word certifies, then serves the pasuk."""
    s = desk_setup
    pasuk1 = [w for w in s["words"] if w.pasuk_index == 1]
    c = as_editor(client)
    lid, uid = s["learner"].id, s["unit"].id

    for w in pasuk1[:-1]:
        c.post(f"/desk/words/{w.id}/approve")
        lesson = client.get(f"/api/learners/{lid}/lesson?unit_id={uid}"
                            ).get_json()["words"]
        assert lesson == [], "pasuk served before its last word was certified"

    resp = c.post(f"/desk/words/{pasuk1[-1].id}/approve")
    assert resp.get_json()["pasuk_servable"] is True
    lesson = client.get(f"/api/learners/{lid}/lesson?unit_id={uid}"
                        ).get_json()["words"]
    assert [w["id"] for w in lesson] == [w.id for w in pasuk1]


def test_certify_pasuk_takes_only_the_remainder(client, desk_setup):
    s = desk_setup
    pasuk1 = [w for w in s["words"] if w.pasuk_index == 1]
    c = as_editor(client)
    c.post(f"/desk/words/{pasuk1[0].id}/approve")
    resp = c.post(f"/desk/units/{s['unit'].id}/pasuk/1/certify")
    data = resp.get_json()
    assert data["certified_now"] == len(pasuk1) - 1
    assert data["pasuk_servable"] is True


def test_no_bulk_certification_above_pasuk(app, desk_setup):
    """The only certify-* route in the app is pasuk-sized."""
    certify_rules = [r.rule for r in app.url_map.iter_rules()
                     if r.rule.endswith("/certify")]
    assert certify_rules == ["/desk/units/<int:unit_id>/pasuk/<int:pasuk_index>/certify"]


def test_drill_deck_respects_frontier(client, desk_setup):
    s = desk_setup
    c = as_editor(client)
    c.post(f"/desk/units/{s['unit'].id}/pasuk/1/certify")
    # Pasuk 2 partially certified: its words must not appear as new ground.
    pasuk2 = [w for w in s["words"] if w.pasuk_index == 2]
    c.post(f"/desk/words/{pasuk2[0].id}/approve")
    deck = client.get(
        f"/api/learners/{s['learner'].id}/drill?unit_id={s['unit'].id}&size=40"
    ).get_json()["words"]
    served_pesukim = {w["pasuk_index"] for w in deck}
    assert served_pesukim <= {1}


# --- Decertify ---------------------------------------------------------------

def test_decertify_is_admin_only_with_reason_and_pulls_pasuk(client, desk_setup):
    s = desk_setup
    w = [x for x in s["words"] if x.pasuk_index == 1][0]
    as_editor(client).post(f"/desk/units/{s['unit'].id}/pasuk/1/certify")

    assert as_editor(client).post(f"/desk/words/{w.id}/decertify",
                                  json={"reason": "wrong"}).status_code == 403

    a = as_admin(client)
    assert a.post(f"/desk/words/{w.id}/decertify",
                  json={"reason": ""}).status_code == 400
    resp = a.post(f"/desk/words/{w.id}/decertify",
                  json={"reason": "gloss is simply wrong"})
    assert resp.status_code == 200
    assert not db.session.get(Word, w.id).certified
    # The pasuk left the servable frontier: the learner gets nothing again.
    lesson = client.get(
        f"/api/learners/{s['learner'].id}/lesson?unit_id={s['unit'].id}"
    ).get_json()["words"]
    assert lesson == []
    # And the reason landed in the flag queue.
    f = WordFlag.query.filter_by(word_id=w.id, status="open").one()
    assert "gloss is simply wrong" in f.note


# --- Flag queue --------------------------------------------------------------

def test_flag_lifecycle_edit_and_certify(client, desk_setup):
    s = desk_setup
    w = s["words"][5]
    c = as_editor(client)
    fid = c.post(f"/desk/words/{w.id}/flag",
                 json={"note": "check this shoresh"}).get_json()["flag_id"]
    queue = c.get("/desk/flags").get_json()["flags"]
    assert [f["id"] for f in queue] == [fid]
    assert queue[0]["note"] == "check this shoresh"
    assert len(queue[0]["pasuk"]) == 10  # context pasuk rides along

    resp = c.post(f"/desk/flags/{fid}/resolve",
                  json={"new_gloss": "the fixed gloss"})
    assert resp.get_json()["status"] == "resolved"
    w = db.session.get(Word, w.id)
    assert w.translation == "the fixed gloss"
    assert w.certified  # resolve-by-edit certifies
    assert GlossRevision.query.filter_by(word_id=w.id).count() == 1
    assert c.get("/desk/flags").get_json()["flags"] == []


def test_flag_dismiss_requires_note(client, desk_setup):
    s = desk_setup
    w = s["words"][6]
    c = as_editor(client)
    fid = c.post(f"/desk/words/{w.id}/flag",
                 json={"note": "?"}).get_json()["flag_id"]
    assert c.post(f"/desk/flags/{fid}/resolve", json={}).status_code == 400
    resp = c.post(f"/desk/flags/{fid}/resolve",
                  json={"note": "gloss is fine as is"})
    assert resp.get_json()["status"] == "resolved"
    assert not db.session.get(Word, w.id).certified  # dismissal certifies nothing
    f = db.session.get(WordFlag, fid)
    assert f.resolution_note == "gloss is fine as is"


# --- Progress and the frontier readout ----------------------------------------

def test_progress_meters_and_frontier(client, desk_setup):
    s = desk_setup
    c = as_editor(client)
    c.post(f"/desk/units/{s['unit'].id}/pasuk/2/certify")  # out of order
    view = c.get(f"/desk/units/{s['unit'].id}").get_json()
    prog = view["progress"]
    assert prog["words_certified"] == 10
    assert prog["pesukim_complete"] == 1
    assert prog["frontier_pasuk"] == 0  # pasuk 1 still open: no contiguous prefix
    c.post(f"/desk/units/{s['unit'].id}/pasuk/1/certify")
    prog = c.get(f"/desk/units/{s['unit'].id}").get_json()["progress"]
    assert prog["frontier_pasuk"] == 2


# --- No certification path from the learner side ------------------------------

def test_learner_endpoints_cannot_certify(client, desk_setup):
    """Exercise every learner-side write while a pasuk is fully draft and
    prove the words table's certification state never moves."""
    s = desk_setup
    as_editor(client).post(f"/desk/units/{s['unit'].id}/pasuk/1/certify")
    client.post("/api/staff/logout")

    lid, uid = s["learner"].id, s["unit"].id
    sid = client.post(f"/api/learners/{lid}/sessions",
                      json={"mode": "learn", "unit_id": uid}
                      ).get_json()["session_id"]
    draft = [w for w in s["words"] if w.pasuk_index == 2][0]
    served = [w for w in s["words"] if w.pasuk_index == 1][0]

    before = {w.id: w.certified for w in Word.query.all()}
    client.post(f"/api/learners/{lid}/reveal",
                json={"word_id": served.id, "session_id": sid})
    client.post(f"/api/learners/{lid}/attempts",
                json={"word_id": served.id, "session_id": sid,
                      "correct": True, "response_ms": 500, "certified": True})
    assert client.post(f"/api/learners/{lid}/reveal",
                       json={"word_id": draft.id, "session_id": sid}
                       ).status_code == 403
    client.post(f"/api/register", json={
        "first_name": "A", "last_name": "B", "cell": "1",
        "email": "a@b.org", "certified": True})
    after = {w.id: w.certified for w in Word.query.all()}
    assert before == after
