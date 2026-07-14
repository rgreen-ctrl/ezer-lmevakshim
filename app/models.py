from datetime import datetime, timezone

from app import db


def utcnow():
    return datetime.now(timezone.utc)


class Learner(db.Model):
    __tablename__ = "learners"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    cell = db.Column(db.String(32), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True)
    # Highest unlocked rung (tracks.rung_order). Rung 1 is open on signup.
    current_rung = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    sessions = db.relationship("Session", backref="learner", lazy="dynamic")
    attempts = db.relationship("Attempt", backref="learner", lazy="dynamic")


class Staff(db.Model):
    """Editor/admin accounts. Editors are writers — they change what every
    learner will be taught — so they carry real credentials (bcrypt) even in
    the pilot. Learners never get rows here."""

    __tablename__ = "staff"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # editor | admin
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class Track(db.Model):
    """A rung of the ladder: Chumash, Pirkei Avos, Eilu Metzios."""

    __tablename__ = "tracks"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(40), nullable=False, unique=True)
    name = db.Column(db.String(120), nullable=False)
    rung_order = db.Column(db.Integer, nullable=False, unique=True)

    units = db.relationship(
        "Unit", backref="track", order_by="Unit.order_index", lazy="dynamic"
    )


class Unit(db.Model):
    """A parsha, perek, or sugya within a track."""

    __tablename__ = "units"

    id = db.Column(db.Integer, primary_key=True)
    track_id = db.Column(db.Integer, db.ForeignKey("tracks.id"), nullable=False)
    kind = db.Column(db.String(20), nullable=False)  # parsha | perek | sugya
    name = db.Column(db.String(120), nullable=False)
    order_index = db.Column(db.Integer, nullable=False)

    words = db.relationship(
        "Word", backref="unit", order_by="Word.position", lazy="dynamic"
    )


class Word(db.Model):
    """Read-only projection of the interlinear store. This app never edits
    hebrew/translation/shoresh/certified — the editor app is the only writer."""

    __tablename__ = "words"

    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("units.id"), nullable=False)
    ref = db.Column(db.String(60), nullable=False)  # e.g. "Bereishis 6:9"
    pasuk_index = db.Column(db.Integer, nullable=False)  # ordinal pasuk in unit
    position = db.Column(db.Integer, nullable=False)  # ordinal word in unit
    aliyah = db.Column(db.Integer)  # milestone level within the parsha (1-7)
    hebrew = db.Column(db.String(120), nullable=False)
    translation = db.Column(db.String(255), nullable=False)  # literal/shoresh gloss
    shoresh = db.Column(db.String(60))
    # Contextual translation: the word rendered in full with its prefix and
    # suffix folded in (e.g. "in his generations"), a DRAFT for editor review,
    # distinct from and never overwriting the literal `translation`. Flagged
    # words are the ones an editor should look at first (verbs, particles,
    # recasts, proper names, thin coverage).
    contextual_translation = db.Column(db.String(255))
    contextual_flagged = db.Column(db.Boolean, nullable=False, default=False)
    contextual_note = db.Column(db.String(255))  # why flagged / source note
    # Grounded, source-labeled suggestion set (JSON list of
    # {text, source_label, recast}) an editor taps to fill the contextual
    # field. Read-only reference data; tapping never approves/certifies.
    suggestions = db.Column(db.Text)
    # draft -> certified moves ONLY through the desk endpoints; the importer
    # and the learner app never touch these three columns.
    certified = db.Column(db.Boolean, nullable=False, default=False)
    certified_by = db.Column(db.Integer, db.ForeignKey("staff.id"))
    certified_at = db.Column(db.DateTime)

    __table_args__ = (db.UniqueConstraint("unit_id", "position"),)


class Session(db.Model):
    __tablename__ = "sessions"

    id = db.Column(db.Integer, primary_key=True)
    learner_id = db.Column(db.Integer, db.ForeignKey("learners.id"), nullable=False)
    unit_id = db.Column(db.Integer, db.ForeignKey("units.id"))
    mode = db.Column(db.String(20), nullable=False)  # learn | drill | verified
    started_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    ended_at = db.Column(db.DateTime)


class Attempt(db.Model):
    """Permanent per-answer history — the core tracking table. Never deleted."""

    __tablename__ = "attempts"

    id = db.Column(db.Integer, primary_key=True)
    learner_id = db.Column(db.Integer, db.ForeignKey("learners.id"), nullable=False)
    word_id = db.Column(db.Integer, db.ForeignKey("words.id"), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=False)
    # know | hesitate | miss — computed server-side, never trusted from the
    # client except tester marks inside a verified test.
    mark = db.Column(db.String(10), nullable=False)
    source = db.Column(db.String(10), nullable=False)  # self | verified
    revealed = db.Column(db.Boolean, nullable=False, default=False)
    response_ms = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    word = db.relationship("Word")

    __table_args__ = (db.Index("ix_attempts_learner_word", "learner_id", "word_id"),)


class WordState(db.Model):
    """Per-learner drill-pool state for a word."""

    __tablename__ = "word_state"

    id = db.Column(db.Integer, primary_key=True)
    learner_id = db.Column(db.Integer, db.ForeignKey("learners.id"), nullable=False)
    word_id = db.Column(db.Integer, db.ForeignKey("words.id"), nullable=False)
    in_pool = db.Column(db.Boolean, nullable=False, default=False)
    pool_entered_at = db.Column(db.DateTime)
    due_at = db.Column(db.DateTime)
    interval_step = db.Column(db.Integer, nullable=False, default=0)
    # Consecutive fast-correct drill answers; graduation needs 2 on different days.
    know_streak = db.Column(db.Integer, nullable=False, default=0)
    last_fast_correct_on = db.Column(db.Date)
    graduated_at = db.Column(db.DateTime)

    word = db.relationship("Word")

    __table_args__ = (db.UniqueConstraint("learner_id", "word_id"),)


class GlossRevision(db.Model):
    """Permanent audit trail of gloss edits. Every change to a word's gloss
    writes a row here — nothing is edited in place without one, and rows are
    never deleted."""

    __tablename__ = "gloss_revisions"

    id = db.Column(db.Integer, primary_key=True)
    word_id = db.Column(db.Integer, db.ForeignKey("words.id"), nullable=False)
    old_gloss = db.Column(db.String(255), nullable=False)
    new_gloss = db.Column(db.String(255), nullable=False)
    editor_id = db.Column(db.Integer, db.ForeignKey("staff.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    word = db.relationship("Word")
    editor = db.relationship("Staff")


class WordFlag(db.Model):
    """The reader-flag healing loop: a questioned gloss awaiting a second
    opinion. Rows are never deleted — resolution is a status change."""

    __tablename__ = "word_flags"

    id = db.Column(db.Integer, primary_key=True)
    word_id = db.Column(db.Integer, db.ForeignKey("words.id"), nullable=False)
    raised_by_kind = db.Column(db.String(10), nullable=False)  # learner | editor
    raised_by_id = db.Column(db.Integer, nullable=False)
    note = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(10), nullable=False, default="open")  # open | resolved
    resolved_by = db.Column(db.Integer, db.ForeignKey("staff.id"))
    resolved_at = db.Column(db.DateTime)
    resolution_note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    word = db.relationship("Word")


class Promotion(db.Model):
    """A verified-test result. Only a passed Promotion unlocks the next rung."""

    __tablename__ = "promotions"

    id = db.Column(db.Integer, primary_key=True)
    learner_id = db.Column(db.Integer, db.ForeignKey("learners.id"), nullable=False)
    track_id = db.Column(db.Integer, db.ForeignKey("tracks.id"), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=False)
    tester_name = db.Column(db.String(120), nullable=False)
    words_dealt = db.Column(db.Integer, nullable=False)
    fails = db.Column(db.Integer, nullable=False)
    hesitations = db.Column(db.Integer, nullable=False)
    passed = db.Column(db.Boolean, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
