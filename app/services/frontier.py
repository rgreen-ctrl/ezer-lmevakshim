"""The certified frontier.

A pasuk is servable to learners the moment its LAST word is certified —
never earlier. The frontier readout is the last pasuk of the contiguous
certified prefix: the line the editors have cleared for the boys climbing
behind them.
"""

from sqlalchemy import case, func

from app import db
from app.models import Word


def servable_pasuk_indexes(unit_id):
    """Pasuk indexes in which every word is certified."""
    rows = (
        db.session.query(
            Word.pasuk_index,
            func.count(Word.id),
            func.sum(case((Word.certified, 1), else_=0)),
        )
        .filter(Word.unit_id == unit_id)
        .group_by(Word.pasuk_index)
        .all()
    )
    return {p for p, total, certified in rows if total == certified}


def frontier_pasuk(unit_id):
    """Last pasuk of the contiguous certified prefix (0 = nothing servable
    from the start yet)."""
    servable = servable_pasuk_indexes(unit_id)
    pesukim = [
        p for (p,) in db.session.query(Word.pasuk_index)
        .filter(Word.unit_id == unit_id)
        .distinct()
        .order_by(Word.pasuk_index)
    ]
    frontier = 0
    for p in pesukim:
        if p not in servable:
            break
        frontier = p
    return frontier


def unit_progress(unit_id):
    total = Word.query.filter_by(unit_id=unit_id).count()
    certified = Word.query.filter_by(unit_id=unit_id, certified=True).count()
    pesukim = (
        db.session.query(Word.pasuk_index)
        .filter(Word.unit_id == unit_id)
        .distinct()
        .count()
    )
    servable = servable_pasuk_indexes(unit_id)
    return {
        "words_total": total,
        "words_certified": certified,
        "pesukim_total": pesukim,
        "pesukim_complete": len(servable),
        "frontier_pasuk": frontier_pasuk(unit_id),
    }
