import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase
from prometheus_client import Counter, Gauge, Histogram
from tenacity import retry, stop_after_attempt, wait_exponential


class ChannelMonitor:
    def __init__(self, db: AsyncIOMotorDatabase, parser):
        self.db = db
        self.parser = parser
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.states = self.db['channel_states']
        self.vacancies = self.db['vacancies']
        self.channel_metrics = {}
        asyncio.create_task(self._init_collections())
        self._setup_metrics()

    def _init_channel_metrics(self, channel_id: str):
        """Инициализация метрик для канала."""
        if channel_id not in self.channel_metrics:
            self.logger.info("Initializing metrics for channel %s", channel_id)
            self.channel_metrics[channel_id] = {
                'messages_processed': self.channel_messages.labels(channel_id=channel_id),
                'parse_errors': self.channel_errors.labels(channel_id=channel_id),
                'last_success': self.channel_last_success.labels(channel_id=channel_id),
                'active': self.channel_status.labels(channel_id=channel_id)
            }

    async def get_last_message_id(self, channel_id: str) -> int:
        doc = await self.states.find_one({"channel_id": channel_id})
        last_id = doc["last_message_id"] if doc else 0
        self.logger.info("Last message ID for channel %s: %d",
                         channel_id, last_id)
        return last_id

    async def update_last_message_id(self, channel_id: str, message_id: int):
        await self.states.update_one(
            {"channel_id": channel_id},
            {"$set": {
                "last_message_id": message_id,
                "updated_at": datetime.utcnow()
            }},
            upsert=True
        )
        self.logger.info("Updated last message ID for channel %s to %d",
                         channel_id, message_id)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def process_message(self, message, channel_id: str):
        try:
            msg_id = getattr(message, 'id', 'unknown')
            self.logger.info("Processing message %s from channel %s",
                             msg_id, channel_id)

            with self.parsing_time.time():
                existing = await self.vacancies.find_one({
                    "telegram_message_id": message.id,
                    "channel_id": channel_id
                })

                if existing:
                    self.logger.info("Message %s from channel %s already exists in database",
                                     msg_id, channel_id)
                    return False

                vacancy_data = await self.parser.parse_vacancy(message)
                if not vacancy_data:
                    self.logger.info("Message %s from channel %s was not parsed as a vacancy",
                                     msg_id, channel_id)
                    return False

                vacancy_dict = self.parser.to_dict(vacancy_data)
                vacancy_dict.update({
                    "telegram_message_id": message.id,
                    "channel_id": channel_id,
                    "parsed_at": datetime.utcnow()
                })

                await self.vacancies.insert_one(vacancy_dict)

                # Обновляем общие метрики
                self.messages_processed.inc()
                self.last_success.set_to_current_time()

                # Обновляем метрики канала
                if channel_id in self.channel_metrics:
                    self.channel_metrics[channel_id]['messages_processed'].inc(
                    )
                    self.channel_metrics[channel_id]['last_success'].set_to_current_time(
                    )

                self.logger.info("Successfully saved vacancy from channel %s: %s (Message ID: %s)",
                                 channel_id, vacancy_dict.get('title', ''), msg_id)
                return True

        except Exception as e:
            self.logger.error("Error processing message %s from channel %s: %s",
                              msg_id, channel_id, str(e))
            self.parse_errors.inc()
            if channel_id in self.channel_metrics:
                self.channel_metrics[channel_id]['parse_errors'].inc()
            raise

    async def monitor_channel(self, channel_id: str):
        try:
            channel_id = self._validate_channel_id(channel_id)
            self.logger.info(
                "Starting monitoring cycle for channel %s", channel_id)

            self._init_channel_metrics(channel_id)

            if channel_id in self.channel_metrics:
                self.channel_metrics[channel_id]['active'].set(1)
                self.logger.info("Channel %s marked as active", channel_id)

            messages = await self.parser.get_channel_messages(channel_id)
            if not messages:
                self.logger.info(
                    "No messages found for channel %s", channel_id)
                return

            self.logger.info("Retrieved %d messages from channel %s",
                             len(messages), channel_id)
            processed = 0
            skipped = 0

            for message in messages:
                if await self.process_message(message, channel_id):
                    processed += 1
                else:
                    skipped += 1

            self.logger.info(
                "Channel %s monitoring cycle complete: processed %d messages, skipped %d messages",
                channel_id, processed, skipped
            )

            if processed:
                await self.update_last_message_id(channel_id, messages[-1].id)

        except Exception as e:
            self.logger.error("Channel monitoring error for %s: %s",
                              channel_id, str(e))
            self.parse_errors.inc()
            if channel_id in self.channel_metrics:
                self.channel_metrics[channel_id]['parse_errors'].inc()
                self.channel_metrics[channel_id]['active'].set(0)
                self.logger.info(
                    "Channel %s marked as inactive due to error", channel_id)

    async def start_monitoring(self, channels: List[str]):
        """
        Начинает мониторинг списка каналов.

        Args:
            channels: Список ID каналов для мониторинга
        """
        self.logger.info("Starting monitoring with provided channels: %s",
                         channels)

        if not channels:
            self.logger.error("No channels provided for monitoring")
            return

        # Валидация списка каналов
        valid_channels = []
        for channel in channels:
            try:
                valid_channel = self._validate_channel_id(channel)
                valid_channels.append(valid_channel)
                self.logger.info(
                    "Channel %s validated successfully", valid_channel)
            except ValueError as e:
                self.logger.error("Invalid channel ID: %s. Error: %s",
                                  channel, str(e))
                continue

        if not valid_channels:
            self.logger.error("No valid channels to monitor")
            return

        self.monitor_status.set(1)
        self.logger.info("Starting monitoring for validated channels: %s",
                         ", ".join(valid_channels))

        try:
            while True:
                self.logger.info(
                    "Starting new monitoring cycle for all channels")
                tasks = [self.monitor_channel(channel)
                         for channel in valid_channels]
                await asyncio.gather(*tasks)
                self.logger.info(
                    "Completed monitoring cycle, waiting 60 seconds")
                await asyncio.sleep(60)
        except Exception as e:
            self.logger.error("Global monitoring error: %s", str(e))
            self.monitor_status.set(0)
            # Устанавливаем статус неактивности для всех каналов
            for channel_id in valid_channels:
                if channel_id in self.channel_metrics:
                    self.channel_metrics[channel_id]['active'].set(0)
                    self.logger.info(
                        "Channel %s marked as inactive", channel_id)
        finally:
            self.monitor_status.set(0)
            self.logger.info("Monitoring stopped")
