"""Certification — the desk's write path, and the ONLY code that ever
touches a word's certified flag.

Locked semantics (see CLAUDE.md):
- Every gloss change writes a gloss_revisions row. No exceptions.
- Editing a draft just updates the draft; editing a certified word takes
  effect immediately, logs its revision, and the word STAYS certified —
  corrections never yank pesukim away from learners mid-parsha.
- Bulk approval exists only at pasuk granularity — the size a person
  actually just read.
- Decertify is admin-only, requires a reason, pulls the owning pasuk off
  the servable frontier, and opens a flag so the word gets fixed.
"""

from app import db
from app.models import GlossRevision, Word, WordFlag
from app.services.pool import utcnow


def approve_word(word, staff, now=None):
    if not (word.translation or "").strip():
        raise ValueError(
            f"{word.ref} word #{word.position}: the draft gloss is empty — "
            "write the gloss before certifying")
    if not word.certified:
        word.certified = True
        word.certified_by = staff.id
        word.certified_at = now or utcnow()
    return word


def edit_gloss(word, staff, new_gloss, now=None):
    """Update a gloss, writing the revision row first. Certification status
    is deliberately untouched: drafts stay drafts, certified stays certified."""
    new_gloss = (new_gloss or "").strip()
    if not new_gloss:
        raise ValueError("new gloss must not be empty")
    if new_gloss == word.translation:
        return None  # nothing changed; no revision row for a no-op
    revision = GlossRevision(
        word_id=word.id,
        old_gloss=word.translation,
        new_gloss=new_gloss,
        editor_id=staff.id,
        created_at=now or utcnow(),
    )
    db.session.add(revision)
    word.translation = new_gloss
    db.session.flush()
    return revision


def certify_pasuk(unit_id, pasuk_index, staff, now=None):
    """Certify every remaining word of ONE pasuk — the only bulk approval
    that exists. Refuses the whole pasuk if any word still has an empty
    gloss, so a blank can never ride a bulk approval into the corpus.
    Returns the number of words certified."""
    words = Word.query.filter_by(
        unit_id=unit_id, pasuk_index=pasuk_index, certified=False
    ).order_by(Word.position).all()
    empty = [w for w in words if not (w.translation or "").strip()]
    if empty:
        raise ValueError(
            f"pasuk has {len(empty)} word(s) with empty glosses — write them "
            f"first: " + ", ".join(f"#{w.position}" for w in empty))
    for w in words:
        approve_word(w, staff, now)
    db.session.flush()
    return len(words)


def decertify_word(word, staff, reason, now=None):
    """Admin-only, deliberate, and loud: the word goes back to draft (its
    pasuk leaves the servable frontier) and an open flag carries the reason
    into the queue so it gets fixed and re-certified."""
    if staff.role != "admin":
        raise PermissionError("decertify is admin-only")
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("decertify requires a reason")
    word.certified = False
    word.certified_by = None
    word.certified_at = None
    flag = WordFlag(
        word_id=word.id,
        raised_by_kind="editor",
        raised_by_id=staff.id,
        note=f"Decertified: {reason}",
        created_at=now or utcnow(),
    )
    db.session.add(flag)
    db.session.flush()
    return flag


def raise_flag(word, staff, note, now=None):
    note = (note or "").strip()
    if not note:
        raise ValueError("a flag needs a note")
    flag = WordFlag(
        word_id=word.id,
        raised_by_kind="editor",
        raised_by_id=staff.id,
        note=note,
        created_at=now or utcnow(),
    )
    db.session.add(flag)
    db.session.flush()
    return flag


def resolve_flag(flag, staff, new_gloss=None, note=None, now=None):
    """Resolve = edit-and-certify, or dismiss-with-note. Flag rows are never
    deleted; resolution is a status change."""
    if flag.status != "open":
        raise ValueError("flag is already resolved")
    now = now or utcnow()
    if new_gloss:
        edit_gloss(flag.word, staff, new_gloss, now)
        approve_word(flag.word, staff, now)
        flag.resolution_note = (note or "").strip() or None
    else:
        note = (note or "").strip()
        if not note:
            raise ValueError("dismissing a flag requires a note")
        flag.resolution_note = note
    flag.status = "resolved"
    flag.resolved_by = staff.id
    flag.resolved_at = now
    db.session.flush()
    return flag
