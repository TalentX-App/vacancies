from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, Field


class SalaryInfo(BaseModel):
    amount: Optional[str] = Field(default="Не вказано")
    currency: Optional[str] = None
    range: Dict[str, Optional[int]] = Field(
        default_factory=lambda: {"min": 0, "max": 0})


class ContactInfo(BaseModel):
    type: str
    value: str


class VacancyBase(BaseModel):
    title: str
    published_date: datetime
    work_format: str
    salary: Optional[SalaryInfo]
    location: str
    company: Optional[str] = Field(default="Не указана")
    company_logo_url: Optional[str] = None
    description: str
    contacts: ContactInfo


class VacancyDB(VacancyBase):
    parsed_at: datetime


class VacancyResponse(VacancyDB):
    id: str


class VacancyList(BaseModel):
    vacancies: list[VacancyResponse]
    total: int = 0


class VacancyCreate(VacancyBase):
    pass


class VacancyUpdate(VacancyBase):
    # Первоначально обязательные поля, а после - необязательные
    title: str  # необязательный параметр
    published_date: datetime  # необязательный параметр
    work_format: Optional[str]  # необязательный параметр
    salary: Optional[SalaryInfo]  # необязательный параметр
    location: Optional[str]  # необязательный параметр
    company: Optional[str]  # необязательный параметр
    description: str  # необязательный параметр
    contacts: Optional[ContactInfo]  # необязательный параметр
