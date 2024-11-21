from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class SalaryInfo(BaseModel):
    amount: str
    currency: Optional[str] = None
    range: Optional[Dict[str, str]] = None


class VacancyBase(BaseModel):
    title: str
    published_date: datetime
    work_format: str
    salary: SalaryInfo
    location: str
    description: str
    raw_text: str
    telegram_message_id: Optional[int] = None
    channel_id: Optional[str] = None
    parsed_at: Optional[datetime] = None


class VacancyResponse(VacancyBase):
    id: str


class VacancyList(BaseModel):
    vacancies: List[VacancyResponse]
    total: int


class VacancyFilter(BaseModel):
    search: Optional[str] = None
    work_format: Optional[str] = None
    location: Optional[str] = None
    salary_min: Optional[str] = None
    salary_max: Optional[str] = None
