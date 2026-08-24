"""Provision a user account for the screening dashboard."""

import argparse
import getpass

from app.api.dependencies import get_user_repository
from app.security.auth import hash_password


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True, help="Username for the new account")
    parser.add_argument("--email", required=True, help="Email for the new account")
    args = parser.parse_args()

    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        raise SystemExit("Passwords do not match")
    if len(password) < 8:
        raise SystemExit("Password must be at least 8 characters")

    repository = get_user_repository()
    if repository.get_by_username(args.username) is not None:
        raise SystemExit(f"User '{args.username}' already exists")
    if repository.get_by_email(args.email.lower()) is not None:
        raise SystemExit(f"Email '{args.email}' already exists")

    repository.create_user(args.username, args.email.lower(), hash_password(password))
    print(f"Created user '{args.username}'")


if __name__ == "__main__":
    main()
