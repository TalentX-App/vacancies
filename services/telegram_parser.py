import asyncio
import json
import re
from dataclasses import dataclass
from typing import List, Optional, Protocol

from anthropic import Anthropic
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import Message

from config import get_settings
from database.mongodb import db
from models.vacancy import Location, Vacancy


class AIParser(Protocol):
    """Protocol for AI parsing service"""

    async def parse_text(self, text: str) -> Optional[dict]:
        """Parse text and return structured data"""
        pass


class MessageParser(Protocol):
    """Protocol for message parsing service"""

    async def parse(self, message: Message, channel_id: str) -> Optional[Vacancy]:
        """Parse message into vacancy"""
        pass


class DatabaseService(Protocol):
    """Protocol for database operations"""

    async def save_vacancy(self, vacancy: Vacancy) -> bool:
        """Save vacancy to database"""
        pass

    async def vacancy_exists(self, message_id: int, channel_id: str) -> bool:
        """Check if vacancy already exists"""
        pass


@dataclass
class TelegramConfig:
    """Configuration for Telegram client"""
    api_id: str
    api_hash: str
    session: str
    channels: List[str]


class AnthropicParser(AIParser):
    """Anthropic Claude implementation of AIParser"""

    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)

    async def parse_text(self, text: str) -> Optional[dict]:
        try:
            response = self.client.messages.create(
                model="claude-3-haiku-20240307",  # Используем более экономичную модель
                max_tokens=1000,  # Уменьшаем максимальное количество токенов
                temperature=0.1,
                system="You are a specialized job vacancy parser for Ukrainian language. Extract and return only valid JSON with key fields.",
                messages=[{
                    "role": "user",
                    "content": f"""Parse this job vacancy text efficiently and return a minimal JSON with key fields:
                    {{
                        "title": "job title",
                        "salary": "salary or null",
                        "location": {{
                            "cities": ["city names"],
                            "is_remote": boolean
                        }},
                        "company": "company name or null",
                        "requirements": ["main requirements"],
                        "conditions": ["main conditions"],
                        "contact": "contact info"
                    }}

                    Text: {text}
                    """
                }]
            )

            content = response.content[0].text
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                json_match = re.search(
                    r'```(?:json)?\s*(.*?)\s*```', content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(1))
                print("Failed to parse JSON response")
                return None

        except Exception as e:
            print(f"Error in parse_with_ai: {str(e)}")
            return None


class MongoDBService(DatabaseService):
    """MongoDB implementation of DatabaseService"""

    def __init__(self, db_client):
        self.db = db_client

    async def save_vacancy(self, vacancy: Vacancy) -> bool:
        try:
            await self.db.vacancies.insert_one(vacancy.dict())
            return True
        except Exception as e:
            print(f"Error saving vacancy: {e}")
            return False

    async def vacancy_exists(self, message_id: int, channel_id: str) -> bool:
        existing = await self.db.vacancies.find_one({
            "telegram_message_id": message_id,
            "channel_id": str(channel_id)
        })
        return existing is not None


class VacancyMessageParser(MessageParser):
    """Implementation of message parser"""

    def __init__(self, ai_parser: AIParser):
        self.ai_parser = ai_parser

    def _format_contact(self, contact: str) -> Optional[str]:
        """Format contact information to Telegram URL"""
        if not contact:
            return None

        contact = contact.strip()
        if contact.startswith('@'):
            return f"https://t.me/{contact[1:]}"
        elif not contact.startswith('https://t.me/'):
            return f"https://t.me/{contact}"
        return contact

    def _is_vacancy_message(self, text: str) -> bool:
        """Check if message looks like a vacancy"""
        # Ключевые индикаторы вакансии
        vacancy_indicators = [
            "ЗП:",
            "Зарплата:",
            "Умови:",
            "Вимоги:",
            "Компанія:",
            "Обов'язки:",
            "Контакти:"
        ]

        # Проверяем наличие минимум 3 индикаторов
        matches = sum(
            1 for indicator in vacancy_indicators if indicator in text)
        return matches >= 3

    async def parse(self, message: Message, channel_id: str) -> Optional[Vacancy]:
        """Parse message into vacancy object"""
        if not message.text:
            return None

        # Проверяем, похоже ли сообщение на вакансию
        if not self._is_vacancy_message(message.text):
            print(
                f"Message {message.id} doesn't look like a vacancy, skipping...")
            return None

        try:
            parsed_data = await self.ai_parser.parse_text(message.text)
            if not parsed_data or not parsed_data.get('title'):
                print(f"Failed to parse {message.id}")
                return None

            # Create Location object
            location = Location(
                cities=parsed_data.get('location', {}).get(
                    'cities', ['Not specified']),
                is_remote=parsed_data.get(
                    'location', {}).get('is_remote', True),
                details=parsed_data.get('location', {}).get('details')
            )

            # Create Vacancy with additional fields
            return Vacancy(
                title=parsed_data.get('title'),
                salary=parsed_data.get('salary'),
                location=location,
                company=parsed_data.get('company'),
                requirements=parsed_data.get('requirements', []),
                conditions=parsed_data.get('conditions', []),
                contact=self._format_contact(parsed_data.get('contact')),
                telegram_message_id=message.id,
                channel_id=str(channel_id),
                url=f"https://t.me/{channel_id}/{message.id}",
                raw_text=message.text,
                experience_level=parsed_data.get('experience_level'),
                employment_type=parsed_data.get('employment_type')
            )

        except Exception as e:
            print(f"Error parsing message {message.id}: {str(e)}")
            return None


class TelegramParser:
    """Main Telegram parser class with improved DI"""

    def __init__(
        self,
        config: TelegramConfig,
        message_parser: MessageParser,
        db_service: DatabaseService,
    ):
        self.config = config
        self.message_parser = message_parser
        self.db_service = db_service
        self.client = TelegramClient(
            StringSession(config.session),
            config.api_id,
            config.api_hash
        )
        self.channels = config.channels
        self._processing = False

    async def start_client(self):
        """Start Telegram client if not connected"""
        if not self.client.is_connected():
            await self.client.start()
            print("Telegram client connected!")

    async def stop_client(self):
        """Gracefully stop the client"""
        if self.client and self.client.is_connected():
            await self.client.disconnect()
            print("Telegram client disconnected!")

    async def start_periodic_parsing(self):
        """Start periodic parsing with improved error handling"""
        self._processing = True
        while self._processing:
            print("Starting periodic parsing...")
            total_processed = 0

            for channel in self.channels:
                if not self._processing:
                    break

                print(f"Fetching messages from channel: {channel}")
                try:
                    await self.fetch_and_save_messages(channel, limit=50)
                    total_processed += 1
                except Exception as e:
                    print(f"Error processing channel {channel}: {e}")

                # Rate limiting delay between channels
                await asyncio.sleep(5)

            print(f"Completed  {total_processed} channels.")
            # Wait before next round (5 minutes)
            await asyncio.sleep(300)

    async def stop_parsing(self):
        """Stop the parsing process"""
        self._processing = False
        await self.stop_client()

    async def fetch_and_save_messages(self, channel_id: str, limit: int = 10):
        """Fetch and save messages with improved error handling"""
        await self.start_client()

        try:
            # Handle numeric channel IDs
            if channel_id.startswith('-100'):
                peer = int(channel_id)
            else:
                try:
                    peer = int(channel_id)
                    # Add -100 prefix for supergroup/channel IDs
                    peer = int(f"-100{str(peer).replace('-100', '')}")
                except ValueError:
                    # If not numeric, treat as username
                    peer = channel_id

            try:
                channel_entity = await self.client.get_entity(peer)
                print(f"Successfully got entity for channel: {channel_id}")
            except ValueError as e:
                print(f"Error getting channel entity for {channel_id}: {e}")
                return
            except Exception as e:
                print(f"Unexpected error getting channel entity: {e}")
                return

            messages_processed = 0
            messages = []
            # Собираем все сообщения сначала
            async for message in self.client.iter_messages(channel_entity, limit=limit):
                if message and message.text:
                    messages.append(message)

            print(f"Fetched {len(messages)} messages from channel")

            # Обрабатываем сообщения
            for message in messages:
                print(f"Processing message {message.id} from {channel_id}")

                # Check if message already exists
                exists = await self.db_service.vacancy_exists(message.id, channel_id)
                if exists:
                    print(f"Message {message.id} already exists, skipping...")
                    continue

                # Parse and save new vacancy
                try:
                    vacancy = await self.message_parser.parse(message, channel_id)
                    if vacancy and await self.db_service.save_vacancy(vacancy):
                        print(f"Vacancy saved: {vacancy.title}")
                        messages_processed += 1
                except Exception as e:
                    print(f"Error processing message {message.id}: {e}")
                    continue

            print(f"Processed {
                  messages_processed} new messages from {channel_id}")

        except Exception as e:
            print(f"Error fetching messages from {channel_id}: {e}")


# Factory function to create TelegramParser instance
def create_telegram_parser(settings) -> TelegramParser:
    """Create and configure TelegramParser instance"""
    config = TelegramConfig(
        api_id=settings.telegram_api_id,
        api_hash=settings.telegram_api_hash,
        session=settings.telegram_session,
        channels=settings.telegram_channels.split(',')
    )

    ai_parser = AnthropicParser(api_key=settings.anthropic_api_key)
    message_parser = VacancyMessageParser(ai_parser)
    db_service = MongoDBService(db.db)

    return TelegramParser(config, message_parser, db_service)
