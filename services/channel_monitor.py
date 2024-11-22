import asyncio
import logging
from datetime import datetime
from typing import List

from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ChannelMonitor:
    def __init__(self, db: AsyncIOMotorDatabase, parser):
        self.db = db
        self.parser = parser
        self.states = self.db['channel_states']
        self.vacancies = self.db['vacancies']

    async def initialize_collections(self):
        """Initialize MongoDB collections with required indexes."""
        try:
            await self.states.create_index([("channel_id", 1)], unique=True)
            await self.vacancies.create_index([
                ("telegram_message_id", 1),
                ("channel_id", 1)
            ], unique=True)
            await self.vacancies.create_index([("published_date", -1)])
            await self.vacancies.create_index([("title", 1)])
            logger.info("MongoDB collections initialized successfully")
        except Exception as e:
            logger.error("Error initializing collections: %s", str(e))
            raise

    async def get_last_message_id(self, channel_id: str) -> int:
        """Get the last processed message ID for a channel."""
        doc = await self.states.find_one({"channel_id": channel_id})
        return doc["last_message_id"] if doc else 0

    async def update_last_message_id(self, channel_id: str, message_id: int):
        """Update the last processed message ID for a channel."""
        await self.states.update_one(
            {"channel_id": channel_id},
            {
                "$set": {
                    "last_message_id": message_id,
                    "updated_at": datetime.utcnow()
                }
            },
            upsert=True
        )

    async def process_message(self, message, channel_id: str) -> bool:
        """Process a single message and save it to the database if it's a valid vacancy."""
        try:
            existing = await self.vacancies.find_one({
                "telegram_message_id": message.id,
                "channel_id": channel_id
            })

            if existing:
                logger.info("Message %s already exists in database",
                            str(message.id))
                return False

            vacancy_data = await self.parser.parse_vacancy(message)
            if not vacancy_data:
                logger.info(
                    "Message %s was not parsed as a vacancy", str(message.id))
                return False

            vacancy_dict = self.parser.to_dict(vacancy_data)
            vacancy_dict.update({
                "telegram_message_id": message.id,
                "channel_id": channel_id,
                "parsed_at": datetime.utcnow()
            })

            await self.vacancies.insert_one(vacancy_dict)
            logger.info("Successfully saved vacancy: %s",
                        vacancy_dict.get("title"))
            return True

        except Exception as e:
            logger.error("Error processing message %s: %s",
                         str(message.id), str(e))
            return False

    async def monitor_channel(self, channel_id: str):
        """Monitor a single channel for new vacancies."""
        try:
            logger.info("Starting monitoring for channel %s", channel_id)

            messages = await self.parser.get_channel_messages(channel_id)
            if not messages:
                logger.info("No messages found for channel %s", channel_id)
                return

            processed = 0
            skipped = 0

            for message in messages:
                if await self.process_message(message, channel_id):
                    processed += 1
                else:
                    skipped += 1

            logger.info(
                "Channel %s monitoring complete: processed %d, skipped %d",
                channel_id, processed, skipped
            )

            if processed:
                await self.update_last_message_id(channel_id, messages[-1].id)

        except Exception as e:
            logger.error("Channel monitoring error for %s: %s",
                         channel_id, str(e))

    async def start_monitoring(self, channels: List[str]):
        """Start monitoring for a list of channels."""
        try:
            await self.initialize_collections()

            while True:
                logger.info("Starting monitoring cycle")
                tasks = [self.monitor_channel(channel) for channel in channels]
                await asyncio.gather(*tasks)
                logger.info("Monitoring cycle complete, waiting 60 seconds")
                await asyncio.sleep(60)

        except Exception as e:
            logger.error("Global monitoring error: %s", str(e))
            raise
