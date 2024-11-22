from typing import Optional

from fastapi import APIRouter, Body, Path, Query

from models.schemas import VacancyCreate, VacancyList, VacancyResponse, VacancyUpdate
from services.vacancy_service import (
    create_vacancy_service,
    delete_vacancy_service,
    get_vacancies_list,
    get_vacancy_by_id_service,
    update_vacancy_service,
)

router = APIRouter()


@router.get(
    "/vacancies",
    response_model=VacancyList,
    summary="Получить список вакансий",
    description="Возвращает список вакансий с возможностью фильтрации и пагинации."
)
async def get_vacancies(
    skip: int = Query(
        0, ge=0, description="Количество пропускаемых элементов для пагинации (по умолчанию 0)."),
    limit: int = Query(
        10, ge=1, le=100, description="Максимальное количество вакансий на странице (по умолчанию 10, максимум 100)."),
    company: Optional[str] = Query(
        None, description="Фильтр по названию компании (поиск по подстроке)."),
    specialization: Optional[str] = Query(
        None, description="Фильтр по специализации (поиск по заголовку или описанию вакансии)."),
    salary_min: Optional[int] = Query(
        None, description="Минимальная зарплата."),
    salary_max: Optional[int] = Query(
        None, description="Максимальная зарплата."),
    sort_by: str = Query("published_date", enum=[
                         "published_date", "title"], description="Поле для сортировки."),
    sort_order: int = Query(-1, ge=-1, le=1,
                            description="Порядок сортировки (-1 для убывания, 1 для возрастания).")
):
    return await get_vacancies_list(skip, limit, company, specialization, salary_min, salary_max, sort_by, sort_order)


@router.get(
    "/vacancies/{vacancy_id}",
    response_model=VacancyResponse,
    summary="Получить вакансию по ID",
    description="Возвращает данные конкретной вакансии по её уникальному идентификатору."
)
async def get_vacancy_by_id(
    vacancy_id: str = Path(...,
                           description="Уникальный идентификатор вакансии в базе данных.")
):
    return await get_vacancy_by_id_service(vacancy_id)


@router.post(
    "/vacancies",
    response_model=VacancyResponse,
    summary="Создать новую вакансию",
    description="Создает новую вакансию на основе переданных данных."
)
async def create_vacancy(
    vacancy: VacancyCreate = Body(...)
):
    return await create_vacancy_service(vacancy)


@router.put(
    "/vacancies/{vacancy_id}",
    response_model=VacancyResponse,
    summary="Редактировать вакансию",
    description="Обновляет информацию о вакансии по её уникальному идентификатору."
)
async def update_vacancy(
    vacancy_id: str = Path(...,
                           description="Уникальный идентификатор вакансии"),
    vacancy: VacancyUpdate = Body(...,
                                  description="Данные для обновления вакансии")
):
    """
    Обновляет информацию по вакансии.

    Args:
        vacancy_id: Уникальный идентификатор вакансии
        vacancy: Новые данные для вакансии

    Returns:
        VacancyResponse: Обновленная вакансия
    """
    return await update_vacancy_service(vacancy_id, vacancy)


@router.delete(
    "/vacancies/{vacancy_id}",
    response_model=dict,
    summary="Удалить вакансию",
    description="Удаляет вакансию по её уникальному идентификатору."
)
async def delete_vacancy(
    vacancy_id: str = Path(...,
                           description="Уникальный идентификатор вакансии.")
):
    return await delete_vacancy_service(vacancy_id)
