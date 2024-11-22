import asyncio
import logging
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from api.routes import router as api_router
from config import get_settings
from database.mongodb import db
from services.channel_monitor import ChannelMonitor
from services.vacancy_parser import VacancyParser

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

settings = get_settings()


def validate_channels(channels_str: str) -> List[str]:
    """
    Валидация и нормализация списка каналов из переменной окружения.
    """
    if not channels_str:
        raise ValueError("TELEGRAM_CHANNELS environment variable is empty")

    # Разделяем строку на список каналов
    channels = [ch.strip() for ch in channels_str.split(',')]

    # Удаляем пустые значения
    channels = [ch for ch in channels if ch]

    if not channels:
        raise ValueError("No valid channel IDs found in TELEGRAM_CHANNELS")

    # Нормализуем ID каналов
    normalized_channels = []
    for channel in channels:
        try:
            # Убираем возможный префикс -100 если он есть
            clean_id = channel.replace('-100', '')
            # Убираем все нецифровые символы
            clean_id = ''.join(filter(str.isdigit, clean_id))
            if clean_id:
                normalized_channels.append(clean_id)
            else:
                logger.warning(f"Invalid channel ID format: {channel}")
        except Exception as e:
            logger.error(f"Error processing channel ID {channel}: {e}")

    if not normalized_channels:
        raise ValueError("No valid channel IDs after normalization")

    logger.info(f"Validated channels: {normalized_channels}")
    return normalized_channels


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logger.info("Starting application initialization")

        # Подключаемся к базе данных
        logger.info("Connecting to MongoDB")
        await db.connect_to_database()

        # Инициализируем парсер
        logger.info("Initializing VacancyParser")
        parser = VacancyParser(api_key=settings.anthropic_api_key)
        await parser.init_telegram(
            settings.telegram_session,
            settings.telegram_api_id,
            settings.telegram_api_hash
        )

        # Валидируем каналы
        try:
            channels = validate_channels(settings.telegram_channels)
            logger.info(f"Starting monitoring for channels: {channels}")
        except ValueError as e:
            logger.error(f"Channel validation error: {e}")
            raise

        # Инициализируем монитор
        logger.info("Initializing ChannelMonitor")
        monitor = ChannelMonitor(db.db, parser)

        # Запускаем мониторинг
        monitor_task = asyncio.create_task(monitor.start_monitoring(channels))
        logger.info("Monitoring task started")

        yield

        # Graceful shutdown
        logger.info("Starting graceful shutdown")
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            logger.info("Monitoring task cancelled successfully")

        await db.close_database_connection()
        logger.info("Application shutdown complete")

    except Exception as e:
        logger.error(f"Error during application lifecycle: {e}")
        raise


app = FastAPI(
    title="TalentX Vacancies API",
    description="API for monitoring and parsing remote job vacancies from Telegram channels",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    return {
        "message": "API is running",
        "status": "ok",
        "version": "1.0.0"
    }


# Add Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Добавляем CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем маршруты API
app.include_router(api_router, prefix="/api")


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting uvicorn server")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=10000,
        reload=True,
        log_level="info"
    )
