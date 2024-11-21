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
    company: str
    description: str
    contacts: str
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
                                "company": "company name if present",
                                "work_format": "Віддаленно/Офіс/Гібрид",
                                "salary": {{
                                    "amount": "amount range or single value or 'Не указано'",
                                    "currency": "UAH/USD/EUR or null",
                                    "range": {{
                                        "min": "minimum value or 0",
                                        "max": "maximum value or 0"
                                    }}
                                }},
                                "location": "work location or 'Не указано'",
                                "description": "brief description of responsibilities (max 300 chars)",
                                "contacts": {{
                                    "type": "telegram_username/phone/link/email",
                                    "value": "actual contact value without @ for telegram usernames"
                                }}
                            }}

                            For contacts field, pay special attention to:
                            - Telegram usernames starting with @ (e.g. username)
                            - Phone numbers in any format
                            - Links (https:// or http://)
                            - Email addresses

                            Text:
                            {text}

                            Return ONLY valid JSON without any comments."""
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

            # Обработка зарплаты:
            salary = parsed.get('salary', {})
            salary_range = salary.get('range', {'min': 0, 'max': 0})

            # Если min или max диапазона отсутствуют, заменяем на 0
            min_salary = salary_range.get('min', 0)
            max_salary = salary_range.get('max', 0)

            # Обеспечиваем, чтобы min и max были целыми числами
            if min_salary is None:
                min_salary = 0
            if max_salary is None:
                max_salary = 0

            # Обработка компании: если её нет, подставляем "Не указано"
            company = parsed.get('company') or 'Не указано'

            return VacancyData(
                title=parsed['title'],
                published_date=message.date,
                work_format=parsed['work_format'],
                salary={
                    "amount": salary.get("amount", "Не указано"),
                    "currency": salary.get("currency", None),
                    "range": {"min": min_salary, "max": max_salary}
                },
                location=parsed['location'],
                company=company,  # всегда строка, либо значение по умолчанию
                description=parsed['description'],
                contacts=parsed['contacts'],
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
            "contacts": data.contacts,
            "raw_text": data.raw_text
        }
