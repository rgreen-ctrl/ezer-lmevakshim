"""Create a staff (editor/admin) account — the human step that seeds the desk.

Usage:
    python3 scripts/create_staff.py --name "R' Ploni" --email ploni@example.org --role admin

The password is read from the STAFF_PASSWORD environment variable if set,
otherwise prompted for interactively (never passed on the command line,
where it would land in shell history).
"""

import argparse
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app, db
from app.auth import ROLES, create_staff


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", required=True, choices=ROLES)
    args = parser.parse_args()

    password = os.environ.get("STAFF_PASSWORD") or getpass.getpass(
        "Password (min 8 chars): ")

    app = create_app()
    with app.app_context():
        staff = create_staff(args.name, args.email, password, args.role)
        db.session.commit()
        print(f"Created {staff.role} account #{staff.id} for {staff.email}.")


if __name__ == "__main__":
    main()
