import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router as api_router
from config import get_settings
from database.mongodb import db
from services.monitor import TelegramMonitor
from services.vacancy_parser import VacancyParser

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await db.connect_to_database()

    # Initialize parser and monitor
    parser = VacancyParser(api_key=settings.anthropic_api_key)
    monitor = TelegramMonitor(parser)

    # Start monitoring task
    monitor_task = asyncio.create_task(monitor.start())

    yield

    # Shutdown
    await monitor.stop()
    await monitor_task
    await db.close_database_connection()

app = FastAPI(
    title="Job Vacancies API",
    description="API for parsing and monitoring job vacancies",
    version="2.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
