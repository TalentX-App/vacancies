from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.schemas import VacancyList, VacancyResponse
from config import get_settings
from database.mongodb import db
from services.vacancy_parser import VacancyParser

settings = get_settings()
router = APIRouter()


async def get_parser() -> VacancyParser:
    parser = VacancyParser(api_key=settings.anthropic_api_key)
    await parser.init_telegram(
        settings.telegram_session,
        settings.telegram_api_id,
        settings.telegram_api_hash
    )
    return parser


@router.post("/parse-latest/{channel_id}")
async def parse_latest_vacancy(
    channel_id: str,
    parser: VacancyParser = Depends(get_parser)
):
    try:
        # Get latest message
        messages = await parser.get_channel_messages(channel_id, limit=1)
        if not messages:
            raise HTTPException(status_code=404, detail="No messages found")

        message = messages[0]

        # Check if already exists
        existing = await db.db.vacancies.find_one({
            "telegram_message_id": message.id,
            "channel_id": channel_id
        })

        if existing:
            return {
                "status": "skipped",
                "message": "Vacancy already exists",
                "vacancy_id": str(existing["_id"])
            }

        # Parse vacancy
        vacancy_data = await parser.parse_vacancy(message)
        if not vacancy_data:
            raise HTTPException(
                status_code=400, detail="Failed to parse vacancy")

        # Prepare for database
        vacancy_dict = parser.to_dict(vacancy_data)
        vacancy_dict.update({
            "telegram_message_id": message.id,
            "channel_id": channel_id,
            "parsed_at": datetime.utcnow()
        })

        # Save to database
        result = await db.db.vacancies.insert_one(vacancy_dict)

        return {
            "status": "success",
            "message": "Vacancy parsed successfully",
            "vacancy_id": str(result.inserted_id),
            "preview": message.text[:100] + "..."
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await parser.close_telegram()


@router.get("/vacancies/", response_model=VacancyList)
async def get_vacancies(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    work_format: Optional[str] = None,
    location: Optional[str] = None,
    sort_by: str = Query("published_date", enum=["published_date", "title"]),
    sort_order: int = Query(-1, ge=-1, le=1)
):
    query = {}

    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}}
        ]

    if work_format:
        query["work_format"] = {"$regex": work_format, "$options": "i"}

    if location:
        query["location"] = {"$regex": location, "$options": "i"}

    total = await db.db.vacancies.count_documents(query)
    cursor = db.db.vacancies.find(query)\
        .skip(skip)\
        .limit(limit)\
        .sort(sort_by, sort_order)

    vacancies = []
    async for doc in cursor:
        # Convert salary range values to strings if they are integers
        if isinstance(doc.get("salary", {}).get("range", {}).get("min"), int):
            doc["salary"]["range"]["min"] = str(
                doc["salary"]["range"].get("min"))
        if isinstance(doc.get("salary", {}).get("range", {}).get("max"), int):
            doc["salary"]["range"]["max"] = str(
                doc["salary"]["range"].get("max"))

        doc["id"] = str(doc["_id"])
        del doc["_id"]
        try:
            vacancies.append(VacancyResponse(**doc))
        except Exception as e:
            print(f"Error creating VacancyResponse: {e}")

    return VacancyList(vacancies=vacancies, total=total)
