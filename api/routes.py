from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from api.schemas import VacancyFilter, VacancyList, VacancyResponse
from database.mongodb import db
from models.vacancy import Vacancy

router = APIRouter()


@router.get("/vacancies/", response_model=VacancyList)
async def get_vacancies(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    company: Optional[str] = None,
    location: Optional[str] = None
):
    """Get list of vacancies with filtering options"""
    query = {}

    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}}
        ]

    if company:
        query["company"] = {"$regex": company, "$options": "i"}

    if location:
        query["location"] = {"$regex": location, "$options": "i"}

    total = await db.db.vacancies.count_documents(query)
    cursor = db.db.vacancies.find(query).skip(
        skip).limit(limit).sort("posted_date", -1)

    vacancies = []
    async for doc in cursor:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
        vacancies.append(VacancyResponse(**doc))

    return VacancyList(vacancies=vacancies, total=total)


@router.get("/vacancies/{vacancy_id}", response_model=VacancyResponse)
async def get_vacancy(vacancy_id: str):
    """Get specific vacancy by ID"""
    from bson import ObjectId

    try:
        vacancy = await db.db.vacancies.find_one({"_id": ObjectId(vacancy_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid vacancy ID")

    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")

    vacancy["id"] = str(vacancy["_id"])
    del vacancy["_id"]
    return VacancyResponse(**vacancy)


@router.get("/vacancies/stats/companies", response_model=List[dict])
async def get_companies_stats():
    """Get statistics about companies and their vacancy counts"""
    pipeline = [
        {"$group": {"_id": "$company", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]

    stats = []
    async for doc in db.db.vacancies.aggregate(pipeline):
        if doc["_id"]:  # Skip None/empty company names
            stats.append(
                {"company": doc["_id"], "vacancy_count": doc["count"]})

    return stats


@router.get("/vacancies/stats/locations", response_model=List[dict])
async def get_locations_stats():
    """Get statistics about locations and their vacancy counts"""
    pipeline = [
        {"$group": {"_id": "$location", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]

    stats = []
    async for doc in db.db.vacancies.aggregate(pipeline):
        if doc["_id"]:  # Skip None/empty locations
            stats.append(
                {"location": doc["_id"], "vacancy_count": doc["count"]})

    return stats
