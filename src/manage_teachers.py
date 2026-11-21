"""Provision teacher accounts for the activities application."""

import argparse
import json
import os
from getpass import getpass

from app import TEACHERS_FILE, hash_password, load_teacher_accounts


def main() -> None:
    parser = argparse.ArgumentParser(description="Add a teacher login account.")
    parser.add_argument("username", help="Username assigned to the teacher")
    args = parser.parse_args()
    username = args.username.strip()
    if not username:
        parser.error("Username cannot be empty.")

    if TEACHERS_FILE.exists():
        try:
            teachers = load_teacher_accounts()
        except (json.JSONDecodeError, RuntimeError) as error:
            parser.error(f"Invalid teacher configuration in {TEACHERS_FILE}: {error}")
    else:
        teachers = []
    if any(account["username"] == username for account in teachers):
        parser.error(f"Teacher account '{username}' already exists.")

    password = getpass("Password: ")
    if not password:
        parser.error("Password cannot be empty.")
    if password != getpass("Confirm password: "):
        parser.error("Passwords do not match.")

    teachers.append(
        {"username": username, "password_hash": hash_password(password)}
    )
    temporary_file = TEACHERS_FILE.with_suffix(".json.tmp")
    temporary_file.write_text(
        json.dumps({"teachers": teachers}, indent=2) + "\n", encoding="utf-8"
    )
    os.chmod(temporary_file, 0o600)
    temporary_file.replace(TEACHERS_FILE)


if __name__ == "__main__":
    main()
