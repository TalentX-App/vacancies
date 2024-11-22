from datetime import datetime
from typing import List, Optional

from bson import ObjectId
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


@router.get("/vacancies", response_model=VacancyList)
async def get_vacancies(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    company: Optional[str] = None,
    specialization: Optional[str] = None,
    salary_min: Optional[int] = None,
    salary_max: Optional[int] = None,
    sort_by: str = Query("published_date", enum=["published_date", "title"]),
    sort_order: int = Query(-1, ge=-1, le=1)
):
    query = {}

    # Поиск по компании
    if company:
        query["company"] = {"$regex": company, "$options": "i"}

    # Поиск по специализации
    if specialization:
        query["$or"] = [
            {"title": {"$regex": specialization, "$options": "i"}},
            {"description": {"$regex": specialization, "$options": "i"}}
        ]

    # Фильтрация по зарплате
    if salary_min or salary_max:
        salary_query = {"salary.range": {"$exists": True}}

        if salary_min and salary_max:
            # Оба значения указаны - ищем пересечение диапазонов
            salary_query["$and"] = [
                # минимум вакансии должен быть меньше или равен максимуму фильтра
                {"salary.range.min": {"$lte": int(salary_max)}},
                # максимум вакансии должен быть больше или равен минимуму фильтра
                {"salary.range.max": {"$gte": int(salary_min)}}
            ]
        elif salary_min:
            # Только минимум
            salary_query["salary.range.min"] = {"$lte": int(salary_min)}
        elif salary_max:
            # Только максимум
            salary_query["salary.range.max"] = {"$gte": int(salary_max)}

        query.update(salary_query)

    print("MongoDB Query:", query)  # Отладочный лог

    # Get total count of documents matching query
    total = await db.db.vacancies.count_documents(query)

    # Retrieve vacancies with pagination and sorting
    cursor = db.db.vacancies.find(query)\
        .skip(skip)\
        .limit(limit)\
        .sort(sort_by, sort_order)

    vacancies = []
    async for doc in cursor:
        # Convert MongoDB ObjectId to string for the response
        doc["id"] = str(doc["_id"])
        del doc["_id"]

        try:
            # Create a VacancyResponse from the document data
            vacancies.append(VacancyResponse(**doc))
        except Exception as e:
            print(f"Error creating VacancyResponse: {e}")

    return VacancyList(vacancies=vacancies, total=total)


# Добавляем новый эндпоинт в существующий роутер
@router.get("/vacancies/{vacancy_id}", response_model=VacancyResponse)
async def get_vacancy_by_id(vacancy_id: str):
    try:
        # Проверяем, является ли id валидным ObjectId
        if not ObjectId.is_valid(vacancy_id):
            raise HTTPException(
                status_code=400,
                detail="Invalid vacancy ID format"
            )

        # Ищем вакансию в базе данных
        vacancy = await db.db.vacancies.find_one({"_id": ObjectId(vacancy_id)})

        if not vacancy:
            raise HTTPException(
                status_code=404,
                detail="Vacancy not found"
            )

        # Конвертируем salary range значения в строки, если они целые числа
        if isinstance(vacancy.get("salary", {}).get("range", {}).get("min"), int):
            vacancy["salary"]["range"]["min"] = str(
                vacancy["salary"]["range"].get("min")
            )
        if isinstance(vacancy.get("salary", {}).get("range", {}).get("max"), int):
            vacancy["salary"]["range"]["max"] = str(
                vacancy["salary"]["range"].get("max")
            )

        # Преобразуем MongoDB ObjectId в строку
        vacancy["id"] = str(vacancy["_id"])
        del vacancy["_id"]

        try:
            return VacancyResponse(**vacancy)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error creating vacancy response: {str(e)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )
