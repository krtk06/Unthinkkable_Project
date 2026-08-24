from typing import Any, cast

from pymongo import ASCENDING
from pymongo.database import Database


class UserRepository:
    def __init__(self, database: Database[Any]) -> None:
        self.database = database
        self.users = database["users"]
        self.users.create_index([("username", ASCENDING)], unique=True)
        self.users.create_index([("email", ASCENDING)], unique=True)

    def create_user(self, username: str, email: str, password_hash: str) -> dict[str, Any]:
        record = {
            "username": username,
            "email": email,
            "password_hash": password_hash,
        }
        self.users.insert_one(record)
        return record

    def get_by_username(self, username: str) -> dict[str, Any] | None:
        return cast(dict[str, Any] | None, self.users.find_one({"username": username}))

    def get_by_email(self, email: str) -> dict[str, Any] | None:
        return cast(dict[str, Any] | None, self.users.find_one({"email": email}))
