"""One-off bootstrap: create the initial Desk ADMIN staff account.

Name / email / role are fixed here so there is NO shell quoting to fight.
The password is typed at a prompt and is never taken as an argument,
hardcoded, logged, or printed. Idempotent: if the account already exists it
does nothing.

Run inside the live container:
    railway ssh python scripts/bootstrap_admin.py
"""

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app, db
from app.auth import create_staff
from app.models import Staff

NAME = "Eliyahu Green"
EMAIL = "rgreen@ygby.org"
ROLE = "admin"


def main():
    app = create_app()
    with app.app_context():
        if Staff.query.filter_by(email=EMAIL).first():
            print(f"Staff account for {EMAIL} already exists - nothing to do.")
            return
        try:
            pw = getpass.getpass("Set a password for the Desk admin (min 8 chars): ")
        except Exception:
            pw = input("Set a password for the Desk admin (min 8 chars, visible): ")
        staff = create_staff(NAME, EMAIL, pw, ROLE)
        db.session.commit()
        print(f"Created {staff.role} account #{staff.id} for {staff.email}.")


if __name__ == "__main__":
    main()
