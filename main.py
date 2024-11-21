import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router as api_router
from config import get_settings
from database.mongodb import db
from services.telegram_parser import create_telegram_parser

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await db.connect_to_database()
    parser = create_telegram_parser(settings)
    parsing_task = asyncio.create_task(parser.start_periodic_parsing())
    yield
    # Shutdown
    await parser.stop_parsing()
    await parsing_task
    await db.close_database_connection()

app = FastAPI(title="Telegram Jobs Parser API", lifespan=lifespan)

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
