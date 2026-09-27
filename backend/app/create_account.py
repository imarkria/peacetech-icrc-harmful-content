"""Create an ICRC reviewer or trained volunteer account, or reset its password.

    python -m app.create_account analyst@icrc.org                     # reviewer
    python -m app.create_account volunteer@example.org --role volunteer

The password is asked in the terminal, never passed on the command line.
"""

import argparse
import getpass

from sqlalchemy import func, select

from .database import SessionLocal, initialize_database
from .models import User, UserRole
from .security import hash_password

MIN_PASSWORD_LENGTH = 12


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("email")
    parser.add_argument("--role", choices=[r.value.lower() for r in UserRole], default="reviewer")
    args = parser.parse_args()

    password = getpass.getpass("Password: ")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(f"Use at least {MIN_PASSWORD_LENGTH} characters.")
    if getpass.getpass("Repeat: ") != password:
        raise SystemExit("Passwords do not match.")

    role = UserRole(args.role.upper()).value
    initialize_database()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(func.lower(User.email) == args.email.lower()))
        if user is None:
            db.add(User(email=args.email, password_hash=hash_password(password), role=role))
            print(f"Created {args.role} {args.email}.")
        else:
            user.password_hash = hash_password(password)
            user.role = role
            print(f"Reset the password of {args.email} ({args.role}).")
        db.commit()


if __name__ == "__main__":
    main()
