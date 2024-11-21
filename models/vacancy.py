from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, Field


class SalaryInfo(BaseModel):
    amount: Optional[str] = None  # Зарплата может отсутствовать
    currency: Optional[str] = None
    range: Optional[Dict[str, Optional[int]]] = Field(
        # Диапазон с целыми числами
        default_factory=lambda: {"min": 0, "max": 0})


class ContactInfo(BaseModel):
    type: str
    value: str


class VacancyBase(BaseModel):
    title: str
    published_date: datetime
    work_format: str
    salary: Optional[SalaryInfo] = None  # Поле зарплаты может быть None
    location: str
    # Подставляем "Не указана", если компания равна null
    company: Optional[str] = Field(default="Не указана")
    description: str
    contacts: ContactInfo
    raw_text: str


class VacancyDB(VacancyBase):
    telegram_message_id: int
    channel_id: str
    parsed_at: datetime


class VacancyResponse(VacancyDB):
    id: str


class VacancyList(BaseModel):
    vacancies: list[VacancyResponse]
    total: int = 0
