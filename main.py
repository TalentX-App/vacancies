import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router as api_router
from config import get_settings
from database.mongodb import db

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logger.info("Starting application initialization")

        # Подключаемся к базе данных
        logger.info("Connecting to MongoDB")
        await db.connect_to_database()

        # Инициализируем парсер
        logger.info("Initializing VacancyParser")

        yield

        # Graceful shutdown
        logger.info("Starting graceful shutdown")
        await db.close_database_connection()
        logger.info("Application shutdown complete")

    except Exception as e:
        logger.error(f"Error during application lifecycle: {e}")
        raise


app = FastAPI(
    title="TalentX Vacancies API",
    description="API for parsing remote job vacancies",
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
