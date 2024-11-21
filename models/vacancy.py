from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, Field


class SalaryInfo(BaseModel):
    amount: str
    currency: Optional[str] = None
    range: Optional[Dict[str, Optional[str]]] = None


class ContactInfo(BaseModel):
    type: str
    value: str


class VacancyBase(BaseModel):
    title: str
    published_date: datetime
    work_format: str
    salary: SalaryInfo
    location: str
    company: str = Field(default="Не указано")
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
