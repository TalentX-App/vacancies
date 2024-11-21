import json
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

import httpx
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import Message


@dataclass
class VacancyData:
    title: str
    published_date: datetime
    work_format: str
    salary: Dict
    location: str
    company: Optional[str]
    description: str
    raw_text: str


class VacancyParser:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client: Optional[TelegramClient] = None

    async def init_telegram(self, session: str, api_id: str, api_hash: str):
        if not self.client:
            self.client = TelegramClient(
                StringSession(session), api_id, api_hash)
            await self.client.start()

    async def close_telegram(self):
        if self.client and self.client.is_connected():
            await self.client.disconnect()

    async def get_channel_messages(self, channel_id: str, limit: int = 1) -> List[Message]:
        try:
            if channel_id.startswith('-100'):
                channel_id = int(channel_id)
            else:
                channel_id = int('-100' + channel_id.strip('-'))

            channel = await self.client.get_entity(channel_id)
            messages = []
            async for message in self.client.iter_messages(channel, limit=limit):
                messages.append(message)
            return messages

        except Exception as e:
            raise Exception(f"Error getting channel messages: {e}")

    async def parse_with_claude(self, text: str, date: datetime) -> Optional[Dict]:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-3-haiku-20240307",
                        "max_tokens": 1000,
                        "temperature": 0,
                        "messages": [{
                            "role": "user",
                            "content": f"""Analyze this job vacancy text and create a JSON with these fields:
                            {{
                                "title": "full job title",
                                "published_date": "{date.isoformat()}",
                                "company": "company name if present or null",
                                "work_format": "remote/office/hybrid",
                                "salary": {{
                                    "amount": "amount range or single value or 'Не указано'",
                                    "currency": "UAH/USD/EUR or null",
                                    "range": {{
                                        "min": "minimum value or null",
                                        "max": "maximum value or null"
                                    }}
                                }},
                                "location": "work location or 'Не указано'",
                                "description": "brief job description (max 300 chars)"
                            }}

                            Text:
                            {text}

                            Return ONLY valid JSON."""
                        }]
                    }
                )

                if response.status_code != 200:
                    raise Exception(f"API error: {response.status_code}")

                data = response.json()
                return json.loads(data['content'][0]['text'])

        except Exception as e:
            print(f"Claude API error: {e}")
            return None

    async def parse_vacancy(self, message: Message) -> Optional[VacancyData]:
        if not message.text:
            return None

        try:
            parsed = await self.parse_with_claude(message.text, message.date)
            if not parsed:
                return None

            return VacancyData(
                title=parsed['title'],
                published_date=message.date,
                work_format=parsed['work_format'],
                salary=parsed['salary'],
                location=parsed['location'],
                company=parsed.get('company'),
                description=parsed['description'],
                raw_text=message.text
            )

        except Exception as e:
            print(f"Error parsing vacancy: {e}")
            return None

    def to_dict(self, data: VacancyData) -> dict:
        return {
            "title": data.title,
            "published_date": data.published_date,
            "work_format": data.work_format,
            "salary": data.salary,
            "location": data.location,
            "company": data.company,
            "description": data.description,
            "raw_text": data.raw_text
        }
