from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class Location(BaseModel):
    cities: List[str] = Field(default_factory=lambda: ["Не вказано"])
    is_remote: bool = True
    details: Optional[str] = None

    def dict(self, *args, **kwargs):
        """Custom dict method for MongoDB compatibility"""
        return {
            "cities": self.cities,
            "is_remote": self.is_remote,
            "details": self.details
        }


class Vacancy(BaseModel):
    title: str
    salary: Optional[str] = None
    location: Location
    company: Optional[str] = None
    requirements: List[str] = Field(default_factory=list)
    conditions: List[str] = Field(default_factory=list)
    contact: Optional[str] = None
    telegram_message_id: int
    channel_id: str
    url: Optional[str] = None
    raw_text: str
    posted_date: datetime = Field(default_factory=datetime.utcnow)
    experience_level: Optional[str] = None
    employment_type: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Senior Python Developer",
                "salary": "$100k-$150k",
                "location": {
                    "cities": ["Київ"],
                    "is_remote": True,
                    "details": "Можлива часткова віддалена робота"
                },
                "company": "Tech Corp",
                "requirements": [
                    "5+ years Python experience",
                    "Strong understanding of Django"
                ],
                "conditions": [
                    "Flexible hours",
                    "Medical insurance"
                ],
                "contact": "https://t.me/hr_manager",
                "experience_level": "senior",
                "employment_type": "full-time"
            }
        }
