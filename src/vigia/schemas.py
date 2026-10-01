from typing import Literal

from pydantic import BaseModel, Field, field_validator


Level = Literal["debug", "info", "warning", "error", "critical"]


class EventIn(BaseModel):
    service: str = Field(min_length=1, max_length=120)
    level: Level
    message: str = Field(min_length=1, max_length=4000)

    @field_validator("service", "message")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("O campo não pode conter apenas espaços.")
        return value


class Incident(BaseModel):
    id: int
    service: str
    level: Level
    message: str
    fingerprint: str
    first_seen: str
    last_seen: str
    occurrences: int


class ServiceMetric(BaseModel):
    service: str
    incidents: int
    occurrences: int


class Metrics(BaseModel):
    total_incidents: int
    total_occurrences: int
    by_level: dict[str, int]
    top_services: list[ServiceMetric]