"""Staff authentication: editors and admins.

Editors are writers — they change what every learner will be taught — so
they get real credentials even in the pilot: bcrypt-hashed passwords, a
signed session cookie, logout. Learners stay email-only and hold no staff
session, so every staff-gated route returns 403 to them.
"""

import bcrypt
from flask import Blueprint, abort, g, jsonify, request
from flask import session as http_session

from app import db
from app.models import Staff

auth = Blueprint("auth", __name__)

ROLES = ("editor", "admin")


def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password, password_hash):
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def current_staff():
    staff_id = http_session.get("staff_id")
    return db.session.get(Staff, staff_id) if staff_id else None


def require_staff(role=None):
    """Server-side gate for every desk route and certification endpoint.
    No staff session — learner or anonymous alike — means 403."""
    staff = current_staff()
    if staff is None:
        abort(403)
    if role == "admin" and staff.role != "admin":
        abort(403)
    g.staff = staff
    return staff


def create_staff(name, email, password, role):
    if role not in ROLES:
        raise ValueError(f"role must be one of {ROLES}")
    if not password or len(password) < 8:
        raise ValueError("password must be at least 8 characters")
    if Staff.query.filter_by(email=email.strip().lower()).first():
        raise ValueError("email already has a staff account")
    staff = Staff(
        name=name.strip(),
        email=email.strip().lower(),
        password_hash=hash_password(password),
        role=role,
    )
    db.session.add(staff)
    db.session.flush()
    return staff


@auth.post("/login")
def login():
    data = request.get_json(force=True)
    staff = Staff.query.filter_by(
        email=data.get("email", "").strip().lower()
    ).first()
    if staff is None or not check_password(data.get("password", ""),
                                           staff.password_hash):
        return jsonify({"error": "invalid credentials"}), 401
    http_session["staff_id"] = staff.id
    return jsonify({"staff_id": staff.id, "name": staff.name,
                    "role": staff.role})


@auth.post("/logout")
def logout():
    http_session.pop("staff_id", None)
    return jsonify({"ok": True})


@auth.get("/me")
def me():
    staff = require_staff()
    return jsonify({"staff_id": staff.id, "name": staff.name,
                    "role": staff.role})
