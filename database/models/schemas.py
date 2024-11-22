from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, Field


class SalaryInfo(BaseModel):
    # Зарплата может отсутствовать
    amount: Optional[str] = Field(default="Не вказано")
    currency: Optional[str] = None
    range: Dict[str, Optional[int]] = Field(
        # Диапазон с целыми числами
        default_factory=lambda: {"min": 0, "max": 0}
    )


class ContactInfo(BaseModel):
    type: str
    value: str


class VacancyBase(BaseModel):
    title: str
    published_date: datetime
    work_format: str
    salary: Optional[SalaryInfo]
    location: str
    # Подставляем "Не указана", если компания равна null
    company: Optional[str] = Field(default="Не указана")
    description: str
    contacts: ContactInfo


class VacancyDB(VacancyBase):
    parsed_at: datetime


class VacancyResponse(VacancyDB):
    id: str


class VacancyList(BaseModel):
    vacancies: list[VacancyResponse]
    total: int = 0
