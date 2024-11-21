import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from api.routes import router as api_router
from config import get_settings
from database.mongodb import db
from services.channel_monitor import ChannelMonitor
from services.vacancy_parser import VacancyParser

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect_to_database()

    # Initialize parser
    parser = VacancyParser(api_key=settings.anthropic_api_key)
    await parser.init_telegram(
        settings.telegram_session,
        settings.telegram_api_id,
        settings.telegram_api_hash
    )

    # Initialize monitor with database instance
    # Pass db instance instead of client
    monitor = ChannelMonitor(db.db, parser)

    # Start monitoring
    channels = settings.telegram_channels.split(',')
    monitor_task = asyncio.create_task(monitor.start_monitoring(channels))

    yield

    monitor_task.cancel()
    await db.close_database_connection()

app = FastAPI(title="TalentX Vacancies API", lifespan=lifespan)


@app.get("/")
async def root():
    return {"message": "API is running"}


# Add Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
