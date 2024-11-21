import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional

import prometheus_client
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from prometheus_client import Counter, Gauge, Histogram
from tenacity import retry, stop_after_attempt, wait_exponential


class ChannelMonitor:
    def __init__(self, db: AsyncIOMotorDatabase, parser):
        self.db = db
        self.parser = parser
        self.logger = logging.getLogger(__name__)

        # Initialize collections
        self.states = self.db.get_collection('channel_states')
        self.vacancies = self.db.get_collection('vacancies')

        # Initialize indexes
        asyncio.create_task(self._init_collections())

        self._setup_metrics()

    def _setup_metrics(self):
        """Setup Prometheus metrics"""
        self.messages_processed = Counter(
            'messages_processed_total', 'Number of messages processed')
        self.parse_errors = Counter(
            'parse_errors_total', 'Number of parsing errors')
        self.parsing_time = Histogram(
            'message_parsing_seconds', 'Time spent parsing messages')
        self.monitor_status = Gauge(
            'telegram_monitor_status', 'Monitor running status')
        self.last_success = Gauge(
            'last_successful_parse_time', 'Last successful parse timestamp')

        self.monitor_status.set(0)

    async def _init_collections(self):
        """Initialize collections and indexes"""
        try:
            # Create indexes for channel_states
            await self.states.create_index([("channel_id", 1)], unique=True)

            # Create indexes for vacancies
            await self.vacancies.create_index([
                ("telegram_message_id", 1),
                ("channel_id", 1)
            ], unique=True)

            await self.vacancies.create_index([("published_date", -1)])
            await self.vacancies.create_index([("title", 1)])

            self.logger.info("MongoDB collections initialized successfully")

        except Exception as e:
            self.logger.error(f"Error initializing collections: {e}")
            raise

    async def get_last_message_id(self, channel_id: str) -> int:
        doc = await self.states.find_one({"channel_id": channel_id})
        return doc["last_message_id"] if doc else 0

    async def update_last_message_id(self, channel_id: str, message_id: int):
        await self.states.update_one(
            {"channel_id": channel_id},
            {"$set": {
                "last_message_id": message_id,
                "updated_at": datetime.utcnow()
            }},
            upsert=True
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def process_message(self, message, channel_id: str):
        try:
            with self.parsing_time.time():
                existing = await self.vacancies.find_one({
                    "telegram_message_id": message.id,
                    "channel_id": channel_id
                })

                if existing:
                    return False

                vacancy_data = await self.parser.parse_vacancy(message)
                if not vacancy_data:
                    return False

                vacancy_dict = self.parser.to_dict(vacancy_data)
                vacancy_dict.update({
                    "telegram_message_id": message.id,
                    "channel_id": channel_id,
                    "parsed_at": datetime.utcnow()
                })

                await self.vacancies.insert_one(vacancy_dict)
                self.messages_processed.inc()
                self.last_success.set_to_current_time()

                self.logger.info(f"Saved vacancy from {channel_id}: {
                                 vacancy_dict.get('title')}")
                return True

        except Exception as e:
            self.logger.error(f"Error processing message {message.id}: {e}")
            self.parse_errors.inc()
            raise

    async def monitor_channel(self, channel_id: str):
        try:
            messages = await self.parser.get_channel_messages(channel_id)

            if not messages:
                return

            processed = 0
            for message in messages:
                if await self.process_message(message, channel_id):
                    processed += 1

            if processed:
                await self.update_last_message_id(channel_id, messages[-1].id)
                self.logger.info(
                    f"Processed {processed} new messages from {channel_id}")

        except Exception as e:
            self.logger.error(f"Channel monitoring error: {e}")
            self.parse_errors.inc()

    async def start_monitoring(self, channels: list):
        self.monitor_status.set(1)
        self.logger.info(
            "Starting monitoring for channels: " + ", ".join(channels))

        try:
            while True:
                tasks = [self.monitor_channel(channel) for channel in channels]
                await asyncio.gather(*tasks)
                await asyncio.sleep(60)
        except Exception as e:
            self.logger.error(f"Monitoring error: {e}")
            self.monitor_status.set(0)
        finally:
            self.monitor_status.set(0)

    def get_metrics(self) -> Dict:
        return {
            "messages_processed": self.messages_processed._value.get(),
            "parse_errors": self.parse_errors._value.get(),
            "monitor_status": self.monitor_status._value.get(),
            "last_success": datetime.fromtimestamp(self.last_success._value.get())
        }
