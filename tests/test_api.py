"""End-to-end API flow: register -> learn (reveal) -> drill -> results;
uncertified words are refused everywhere."""


def test_register_and_ladder(client, seeded):
    resp = client.post("/api/register", json={
        "first_name": "Moshe", "last_name": "Katz",
        "cell": "555-0101", "email": "moshe@example.org"})
    assert resp.status_code == 201
    lid = resp.get_json()["learner_id"]

    resp = client.get(f"/api/learners/{lid}/ladder")
    ladder = resp.get_json()["ladder"]
    assert ladder[0]["status"] == "current"

    # Duplicate registration is refused.
    resp = client.post("/api/register", json={
        "first_name": "Moshe", "last_name": "Katz",
        "cell": "555-0101", "email": "moshe@example.org"})
    assert resp.status_code == 409


def test_lesson_ends_at_pasuk_boundary(client, app, seeded):
    s = seeded
    resp = client.get(
        f"/api/learners/{s['learner'].id}/lesson?unit_id={s['unit'].id}")
    words = resp.get_json()["words"]
    lo = app.config["LESSON_MIN_NEW_WORDS"]
    assert len(words) >= min(lo, 30)
    # The last word of the lesson must close its pasuk: the next word in the
    # unit (if any) belongs to a different pasuk.
    last = words[-1]
    following = [w for w in s["words"] if w.position == last["position"] + 1]
    if following:
        assert following[0].pasuk_index != last["pasuk_index"]
    # Learn mode never ships translations in the lesson payload.
    assert "translation" not in words[0]


def test_reveal_returns_translation_and_flags_word(client, seeded):
    s = seeded
    sid = client.post(f"/api/learners/{s['learner'].id}/sessions",
                      json={"mode": "learn", "unit_id": s["unit"].id}
                      ).get_json()["session_id"]
    resp = client.post(f"/api/learners/{s['learner'].id}/reveal", json={
        "word_id": s["words"][0].id, "session_id": sid})
    assert resp.get_json()["translation"] == "word 1"

    # The revealed word now shows up in the drill deck (weak pool).
    resp = client.get(
        f"/api/learners/{s['learner'].id}/drill?unit_id={s['unit'].id}&size=40")
    ids = [w["id"] for w in resp.get_json()["words"]]
    assert s["words"][0].id in ids


def test_uncertified_words_are_refused(client, seeded):
    s = seeded
    sid = client.post(f"/api/learners/{s['learner'].id}/sessions",
                      json={"mode": "learn", "unit_id": s["unit"].id}
                      ).get_json()["session_id"]
    for path, payload in (
        ("reveal", {"word_id": s["uncertified"].id, "session_id": sid}),
        ("attempts", {"word_id": s["uncertified"].id, "session_id": sid,
                      "correct": True, "response_ms": 500}),
    ):
        resp = client.post(f"/api/learners/{s['learner'].id}/{path}", json=payload)
        assert resp.status_code == 403

    # And it never appears in a lesson or drill deck.
    lesson = client.get(
        f"/api/learners/{s['learner'].id}/lesson?unit_id={s['unit'].id}"
    ).get_json()["words"]
    drill = client.get(
        f"/api/learners/{s['learner'].id}/drill?unit_id={s['unit'].id}&size=40"
    ).get_json()["words"]
    assert s["uncertified"].id not in [w["id"] for w in lesson + drill]


def test_results_lists_weak_words(client, seeded):
    s = seeded
    sid = client.post(f"/api/learners/{s['learner'].id}/sessions",
                      json={"mode": "drill", "unit_id": s["unit"].id}
                      ).get_json()["session_id"]
    client.post(f"/api/learners/{s['learner'].id}/attempts", json={
        "word_id": s["words"][0].id, "session_id": sid,
        "correct": True, "response_ms": 800})
    client.post(f"/api/learners/{s['learner'].id}/attempts", json={
        "word_id": s["words"][1].id, "session_id": sid,
        "correct": False, "response_ms": 800})
    data = client.get(
        f"/api/learners/{s['learner'].id}/results?session_id={sid}"
    ).get_json()
    assert data["total"] == 2
    assert data["known"] == 1
    assert [w["mark"] for w in data["weak"]] == ["miss"]
