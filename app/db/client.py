from pymongo import MongoClient
from pymongo.database import Database

from app.config import Settings


def create_mongo_client(settings: Settings) -> MongoClient[dict[str, object]]:
    return MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5_000)


def get_database(
    client: MongoClient[dict[str, object]], settings: Settings
) -> Database[dict[str, object]]:
    return client[settings.mongo_database]


def check_mongo_connection(client: MongoClient[dict[str, object]]) -> None:
    client.admin.command("ping")
