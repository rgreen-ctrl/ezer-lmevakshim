"""The Certification Desk — the only place certification happens.

Every route under /desk is gated by a blueprint-level before_request: no
staff session (learner or anonymous alike) means 403, checked server-side.
D1 ships the gated skeleton; the review views, word actions, and the flag
queue arrive in D2.
"""

from flask import Blueprint, g, jsonify

from app.auth import require_staff
from app.models import Track

desk = Blueprint("desk", __name__)


@desk.before_request
def _gate():
    require_staff()


@desk.get("/")
def home():
    tracks = Track.query.order_by(Track.rung_order).all()
    return jsonify({
        "desk": "The Certification Desk",
        "staff": {"name": g.staff.name, "role": g.staff.role},
        "tracks": [{"id": t.id, "key": t.key, "name": t.name} for t in tracks],
    })
