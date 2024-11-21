from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SalaryRange(BaseModel):
    min: int
    max: int


class SalaryInfo(BaseModel):
    amount: str
    currency: str
    range: SalaryRange


class ContactInfo(BaseModel):
    type: str
    value: str


class VacancyBase(BaseModel):
    title: str
    published_date: datetime
    work_format: str
    salary: SalaryInfo
    location: str
    company: str
    description: str
    contacts: ContactInfo
    raw_text: str
    telegram_message_id: Optional[int] = None
    channel_id: Optional[str] = None
    parsed_at: Optional[datetime] = None


class VacancyResponse(VacancyBase):
    id: str  # Include the id to map to MongoDB's _id


class VacancyList(BaseModel):
    vacancies: list[VacancyResponse]
    total: int
