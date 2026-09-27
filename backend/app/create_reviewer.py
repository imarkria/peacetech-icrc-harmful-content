"""Create a reviewer account, or reset its password.

    python -m app.create_reviewer analyst@icrc.org

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
    args = parser.parse_args()

    password = getpass.getpass("Password: ")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(f"Use at least {MIN_PASSWORD_LENGTH} characters.")
    if getpass.getpass("Repeat: ") != password:
        raise SystemExit("Passwords do not match.")

    initialize_database()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(func.lower(User.email) == args.email.lower()))
        if user is None:
            db.add(User(email=args.email, password_hash=hash_password(password), role=UserRole.REVIEWER.value))
            print(f"Created reviewer {args.email}.")
        else:
            user.password_hash = hash_password(password)
            print(f"Reset the password of {args.email}.")
        db.commit()


if __name__ == "__main__":
    main()
