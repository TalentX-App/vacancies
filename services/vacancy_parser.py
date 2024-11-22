import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import httpx
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import Message

# Настройка логгера
logger = logging.getLogger("vacancy_parser")
logger.setLevel(logging.INFO)


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
        self.logger = logger

    async def init_telegram(self, session: str, api_id: str, api_hash: str):
        if not self.client:
            self.logger.info("Initializing Telegram client")
            self.client = TelegramClient(
                StringSession(session), api_id, api_hash)
            await self.client.start()
            self.logger.info("Telegram client initialized successfully")

    async def close_telegram(self):
        if self.client and self.client.is_connected():
            await self.client.disconnect()
            self.logger.info("Telegram client disconnected")

    async def get_channel_messages(self, channel_id: str, limit: int = 1) -> List[Message]:
        try:
            self.logger.info("Fetching messages from channel %s", channel_id)
            if channel_id.startswith('-100'):
                channel_id = int(channel_id)
            else:
                channel_id = int('-100' + channel_id.strip('-'))

            channel = await self.client.get_entity(channel_id)
            messages = []
            async for message in self.client.iter_messages(channel, limit=limit):
                if message.text:  # Логируем только если есть текст
                    self.logger.debug("Received message %s from channel %s:\n%s...",
                                      message.id, channel_id, message.text[:500])
                messages.append(message)

            self.logger.info("Retrieved %d messages from channel %s",
                             len(messages), channel_id)
            return messages

        except Exception as e:
            self.logger.error("Error getting messages from channel %s: %s",
                              channel_id, str(e))
            raise

    def is_valid_message(self, message: Message) -> Tuple[bool, str]:
        """
        Проверяет, является ли сообщение валидным для парсинга.
        """
        msg_id = getattr(message, 'id', 'unknown')

        # Выводим текст сообщения для отладки
        self.logger.debug("\nProcessing message %s with text:\n%s\n",
                          msg_id, message.text[:200])

        if not message.text:
            self.logger.info("Message %s skipped: No text content", msg_id)
            return False, "Message contains no text"

        if message.media and not message.text:
            self.logger.info("Message %s skipped: Contains only media", msg_id)
            return False, "Message contains only media"

        if len(message.text) < 30:
            self.logger.info("Message %s skipped: Too short (%d chars)",
                             msg_id, len(message.text))
            return False, "Message is too short"

        # Основные ключевые слова для вакансии
        main_keywords = [
            # Украинские
            'вакансія', 'шукаємо', 'потрібен', 'потрібна',
            'відкрита вакансія', 'нова вакансія',
            'запрошуємо', 'приєднуйся', 'у команду', 'в команду',
            'робота', 'пошук', 'відкрита позиція',
            'терміново', 'відгукуйся',
            # Русские
            'вакансия', 'ищем', 'требуется', 'открыта вакансия',
            'ищу', 'нужен', 'нужна', 'требуются', 'открыта позиция',
            'работа', 'поиск', 'срочно', 'откликайся',
            # Английские
            'hiring', 'looking for', 'job opening', 'job opportunity',
            'position', 'vacancy', 'remote job', 'job', 'work'
        ]

        # Ключевые слова для разделов вакансии
        section_keywords = [
            # Украинские
            'вимоги', 'умови', 'обов\'язки', 'досвід', 'компанія',
            'зарплата', 'оплата', 'контакти', 'віддалено', 'локація',
            'пропонуємо', 'чекаємо', 'опис', 'проект', 'графік',
            'навички', 'знання', 'освіта', 'бонуси', 'переваги',
            'досвід', 'зп', 'з/п',
            # Русские
            'требования', 'условия', 'обязанности', 'опыт', 'компания',
            'зарплата', 'оплата', 'контакты', 'удаленно', 'локация',
            'предлагаем', 'ждем', 'описание', 'проект', 'график',
            'навыки', 'знания', 'образование', 'бонусы', 'преимущества',
            'зп', 'з/п',
            # Английские
            'requirements', 'conditions', 'responsibilities', 'experience',
            'company', 'salary', 'payment', 'contacts', 'remote', 'location',
            'offering', 'description', 'project', 'schedule', 'skills',
            'education', 'benefits', 'qualifications', 'stack', 'technologies'
        ]

        # Приводим текст к нижнему регистру для поиска
        text_lower = message.text.lower()

        # Ищем ключевые слова с учетом возможных вариантов регистра
        found_main_keywords = set()
        found_section_keywords = set()

        # Проверяем основные ключевые слова
        for keyword in main_keywords:
            if keyword.lower() in text_lower:
                # Найдем оригинальное слово в тексте для логирования
                found_main_keywords.add(keyword)

        # Проверяем ключевые слова разделов
        for keyword in section_keywords:
            if keyword.lower() in text_lower:
                found_section_keywords.add(keyword)

        # Логируем найденные ключевые слова
        self.logger.debug(
            f"\nFound keywords in message {msg_id}:\n"
            f"Main keywords ({len(found_main_keywords)}): {
                ', '.join(found_main_keywords)}\n"
            f"Section keywords ({len(found_section_keywords)}): {
                ', '.join(found_section_keywords)}\n"
        )

        if not found_main_keywords:
            self.logger.info(
                f"Message {msg_id} skipped: No main job keywords found")
            return False, "No job-related main keywords found"

        if len(found_section_keywords) < 2:
            self.logger.info(
                "Message %s skipped: Not enough section keywords found (found %d): %s",
                msg_id, len(found_section_keywords), ', '.join(
                    found_section_keywords)
            )
            return False, "Not enough vacancy section keywords"

        # Добавим проверку на ключевые слова удаленной работы
        remote_keywords = {
            'віддалено', 'дистанційно', 'remote', 'удаленно', 'дистанционно',
            'віддалена робота', 'удаленная работа', 'remote work', 'працювати з дому',
            'работа из дома', 'work from home', 'home office'
        }

        found_remote_keywords = {
            kw for kw in remote_keywords if kw.lower() in text_lower}

        self.logger.info(
            "Message %s validated successfully:"
            "\nMain keywords (%d): %s"
            "\nSection keywords (%d): %s"
            "\nRemote keywords (%d): %s",
            msg_id,
            len(found_main_keywords), ', '.join(found_main_keywords),
            len(found_section_keywords), ', '.join(found_section_keywords),
            len(found_remote_keywords), ', '.join(found_remote_keywords)
        )
        return True, "Valid message"

    async def parse_with_claude(self, text: str, date: datetime) -> Optional[Dict]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
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
                            "content": f"""Analyze this job vacancy text and create a JSON with these fields.
                            IMPORTANT: Only process remote job vacancies. If the job is not remote or the work format is unclear, return null.
                            Note: Pay special attention to phrases like 'віддалено', 'remote', 'дистанційно', 'remote work', etc.

                            {{
                                "title": "full job title",
                                "published_date": "{date.isoformat()}",
                                "company": "company name if present",
                                "work_format": "Віддаленно/Офіс/Гібрид (must be 'Віддаленно' for valid vacancies)",
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

                            Remember: Only process and return JSON for remote jobs (work_format must be 'Віддаленно').
                            If the job is not remote or format is unclear, return null.
                            Return ONLY valid JSON without any comments."""
                        }]
                    }
                )

                if response.status_code != 200:
                    self.logger.error("Claude API error: %d",
                                      response.status_code)
                    raise Exception("API error: %d" % response.status_code)

                data = response.json()
                result = json.loads(data['content'][0]['text'])

                if result:
                    self.logger.info("Claude successfully parsed the vacancy: %s",
                                     result.get('title', 'No title'))
                else:
                    self.logger.info(
                        "Claude returned null (not a remote vacancy or unclear format)")

                return result

        except Exception as e:
            self.logger.error("Claude API error: %s", str(e))
            return None

    async def parse_vacancy(self, message: Message) -> Optional[VacancyData]:
        msg_id = getattr(message, 'id', 'unknown')
        self.logger.info("Starting to parse message %s", msg_id)

        # Проверяем валидность сообщения
        is_valid, reason = self.is_valid_message(message)
        if not is_valid:
            self.logger.info(
                "Message %s validation failed: %s", msg_id, reason)
            return None

        try:
            parsed = await self.parse_with_claude(message.text, message.date)
            if not parsed:
                self.logger.info(
                    "Message %s: Failed to parse with Claude", msg_id)
                return None

            # Проверяем, что это удаленная вакансия
            if parsed.get('work_format') != 'Віддаленно':
                self.logger.info("Message %s skipped: Not a remote vacancy (format: %s)",
                                 msg_id, parsed.get('work_format'))
                return None

            # Обработка зарплаты
            salary = parsed.get('salary', {})
            salary_range = salary.get('range', {'min': 0, 'max': 0})

            # Если min или max диапазона отсутствуют, заменяем на 0
            min_salary = salary_range.get('min', 0) or 0
            max_salary = salary_range.get('max', 0) or 0

            # Обработка компании: если её нет, подставляем "Не указано"
            company = parsed.get('company') or 'Не указано'

            vacancy_data = VacancyData(
                title=parsed['title'],
                published_date=message.date,
                work_format=parsed['work_format'],
                salary={
                    "amount": salary.get("amount", "Не указано"),
                    "currency": salary.get("currency", None),
                    "range": {"min": min_salary, "max": max_salary}
                },
                location=parsed['location'],
                company=company,
                description=parsed['description'],
                contacts=parsed['contacts'],
                raw_text=message.text
            )

            self.logger.info("Successfully parsed vacancy from message %s: %s",
                             msg_id, vacancy_data.title)
            return vacancy_data

        except Exception as e:
            self.logger.error("Error parsing message %s: %s", msg_id, str(e))
            return None

    def to_dict(self, data: VacancyData) -> dict:
        result = {
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
        self.logger.debug("Converted VacancyData to dict: %s",
                          json.dumps(result, default=str))
        return result
