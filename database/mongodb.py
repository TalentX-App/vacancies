from motor.motor_asyncio import AsyncIOMotorClient

from config import get_settings

settings = get_settings()


class Database:
    client: AsyncIOMotorClient = None
    db = None

    async def connect_to_database(self):
        self.client = AsyncIOMotorClient(settings.mongodb_url)
        self.db = self.client[settings.database_name]
        print("Connected to MongoDB!")

    async def close_database_connection(self):
        if self.client is not None:
            self.client.close()
            print("Closed MongoDB connection!")


db = Database()
