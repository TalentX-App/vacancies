import asyncio
import logging
from datetime import datetime
from typing import List, Optional

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import Message

from config import get_settings
from services.vacancy_parser import VacancyParser
from database.mongodb import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TelegramMonitor:
    def __init__(self, parser: VacancyParser):
        self.settings = get_settings()
        self.parser = parser
        self.client: Optional[TelegramClient] = None
        self.is_running = False
        self.channels = self.settings.telegram_channels.split(',')
        self.last_message_ids = {}

    async def init_client(self):
        if not self.client:
            self.client = TelegramClient(
                StringSession(self.settings.telegram_session),
                self.settings.telegram_api_id,
                self.settings.telegram_api_hash
            )
            await self.client.start()
            logger.info("Telegram client started")

    async def close_client(self):
        if self.client:
            await self.client.disconnect()
            logger.info("Telegram client disconnected")

    async def get_new_messages(self, channel_id: str) -> List[Message]:
        try:
            if channel_id.startswith('-100'):
                peer = int(channel_id)
            else:
                peer = int('-100' + channel_id.strip('-'))

            channel = await self.client.get_entity(peer)
            last_id = self.last_message_ids.get(channel_id, 0)
            
            messages = []
            async for message in self.client.iter_messages(channel, min_id=last_id):
                if message.text:  # Only process messages with text
                    messages.append(message)

            if messages:
                self.last_message_ids[channel_id] = messages[0].id
                
            return messages[::-1]  # Return in chronological order

        except Exception as e:
            logger.error(f"Error getting messages from {channel_id}: {e}")
            return []

    async def process_messages(self, messages: List[Message], channel_id: str):
        for message in messages:
            try:
                # Check if already processed
                existing = await db.db.vacancies.find_one({
                    "telegram_message_id": message.id,
                    "channel_id": channel_id
                })
                
                if existing:
                    continue

                # Parse vacancy
                vacancy_data = await self.parser.parse_vacancy(message)
                if not vacancy_data:
                    continue

                # Save to database
                vacancy_dict = self.parser.to_dict(vacancy_data)
                vacancy_dict.update({
                    "telegram_message_id": message.id,
                    "channel_id": channel_id,
                    "parsed_at": datetime.utcnow()
                })
                
                await db.db.vacancies.insert_one(vacancy_dict)
                logger.info(f"Saved new vacancy from {channel_id}: {vacancy_dict['title']}")

            except Exception as e:
                logger.error(f"Error processing message {message.id}: {e}")

    async def monitor_channels(self):
        try:
            await self.init_client()
            
            while self.is_running:
                for channel_id in self.channels:
                    try:
                        messages = await self.get_new_messages(channel_id)
                        if messages:
                            logger.info(f"Found {len(messages)} new messages in {channel_id}")
                            await self.process_messages(messages, channel_id)
                    except Exception as e:
                        logger.error(f"Error monitoring channel {channel_id}: {e}")
                        continue
                        
                await asyncio.sleep(60)  # Check every minute

        except Exception as e:
            logger.error(f"Monitor error: {e}")
        finally:
            await self.close_client()

    async def start(self):
        logger.info("Starting Telegram monitor")
        self.is_running = True
        await self.monitor_channels()

    async def stop(self):
        logger.info("Stopping Telegram monitor")
        self.is_running = False
        await self.close_client()