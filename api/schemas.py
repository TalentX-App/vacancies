from typing import List, Optional

from pydantic import BaseModel

from models.vacancy import Vacancy


class VacancyResponse(Vacancy):
    id: str


class VacancyList(BaseModel):
    vacancies: List[VacancyResponse]
    total: int


class VacancyFilter(BaseModel):
    search: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    salary_min: Optional[str] = None
    salary_max: Optional[str] = None
