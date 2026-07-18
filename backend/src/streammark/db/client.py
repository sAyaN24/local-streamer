from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from streammark.common.config import Settings


def create_client(settings: Settings) -> AsyncIOMotorClient:
    return AsyncIOMotorClient(settings.mongodb_uri)


def get_database(client: AsyncIOMotorClient, settings: Settings) -> AsyncIOMotorDatabase:
    return client[settings.mongodb_db_name]


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db["users"].create_index("email", unique=True)
    await db["rooms"].create_index("status")
    await db["annotations"].create_index([("room", 1), ("ts", 1)])
