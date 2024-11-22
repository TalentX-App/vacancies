from datetime import datetime
from typing import Optional

from bson import ObjectId
from fastapi import HTTPException

from database.mongodb import db
from models.schemas import VacancyCreate, VacancyList, VacancyResponse, VacancyUpdate


# Получение списка вакансий с фильтрацией
async def get_vacancies_list(skip: int, limit: int, company: Optional[str], specialization: Optional[str],
                             salary_min: Optional[int], salary_max: Optional[int], sort_by: str, sort_order: int):
    query = {}

    # Фильтрация по компании
    if company:
        query["company"] = {"$regex": company, "$options": "i"}

    # Фильтрация по специализации
    if specialization:
        query["$or"] = [
            {"title": {"$regex": specialization, "$options": "i"}},
            {"description": {"$regex": specialization, "$options": "i"}}
        ]

    # Фильтрация по зарплате
    if salary_min or salary_max:
        salary_query = {"salary.range": {"$exists": True}}

        if salary_min and salary_max:
            salary_query["$and"] = [
                {"salary.range.min": {"$lte": int(salary_max)}},
                {"salary.range.max": {"$gte": int(salary_min)}}
            ]
        elif salary_min:
            salary_query["salary.range.min"] = {"$lte": int(salary_min)}
        elif salary_max:
            salary_query["salary.range.max"] = {"$gte": int(salary_max)}

        query.update(salary_query)

    total = await db.db.vacancies.count_documents(query)
    cursor = db.db.vacancies.find(query).skip(
        skip).limit(limit).sort(sort_by, sort_order)

    vacancies = []
    async for doc in cursor:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
        vacancies.append(VacancyResponse(**doc))

    return VacancyList(vacancies=vacancies, total=total)

# Получение информации по конкретной вакансии


async def get_vacancy_by_id_service(vacancy_id: str):
    if not ObjectId.is_valid(vacancy_id):
        raise HTTPException(
            status_code=400, detail="Invalid vacancy ID format")

    vacancy = await db.db.vacancies.find_one({"_id": ObjectId(vacancy_id)})

    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")

    vacancy["id"] = str(vacancy["_id"])
    del vacancy["_id"]
    return VacancyResponse(**vacancy)

# Создание вакансии


async def create_vacancy_service(vacancy_data: VacancyCreate):
    vacancy = vacancy_data.dict()
    vacancy["parsed_at"] = datetime.utcnow()  # Добавляем поле даты создания
    result = await db.db.vacancies.insert_one(vacancy)
    return VacancyResponse(id=str(result.inserted_id), **vacancy)

# Обновление вакансии


async def update_vacancy_service(vacancy_id: str, vacancy_data: VacancyUpdate):
    if not ObjectId.is_valid(vacancy_id):
        raise HTTPException(
            status_code=400, detail="Invalid vacancy ID format")

    update_data = vacancy_data.dict(exclude_unset=True)
    result = await db.db.vacancies.update_one({"_id": ObjectId(vacancy_id)}, {"$set": update_data})

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Vacancy not found")

    updated_vacancy = await db.db.vacancies.find_one({"_id": ObjectId(vacancy_id)})
    updated_vacancy["id"] = str(updated_vacancy["_id"])
    del updated_vacancy["_id"]
    return VacancyResponse(**updated_vacancy)

# Удаление вакансии


async def delete_vacancy_service(vacancy_id: str):
    if not ObjectId.is_valid(vacancy_id):
        raise HTTPException(
            status_code=400, detail="Invalid vacancy ID format")

    result = await db.db.vacancies.delete_one({"_id": ObjectId(vacancy_id)})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Vacancy not found")

    return {"status": "Vacancy deleted successfully"}
