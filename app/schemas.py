from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models import BookingStatus


class ErrorPayload(BaseModel):
    """структура ошибки api"""

    code: str
    message: str
    details: Any = None


class ErrorResponse(BaseModel):
    """обертка для ошибок api"""

    error: ErrorPayload


class BookingCreateRequest(BaseModel):
    """тело запроса на создание бронирования"""

    room_id: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)
    start_at: datetime
    end_at: datetime

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value

    @field_validator("start_at", "end_at")
    @classmethod
    def require_naive_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is not None:
            raise ValueError(
                "timezone-aware datetime is not supported; use naive local datetime"
            )
        return value

    @model_validator(mode="after")
    def validate_interval(self) -> "BookingCreateRequest":
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be greater than start_at")
        return self


class BookingResponse(BaseModel):
    """ответ с данными бронирования"""

    id: int
    room_id: int
    title: str
    start_at: datetime
    end_at: datetime
    status: BookingStatus


class AvailableSlotResponse(BaseModel):
    """один свободный интервал"""

    start_at: datetime
    end_at: datetime


class AvailableSlotsResponse(BaseModel):
    """список свободных интервалов комнаты на дату"""

    room_id: int
    date: date
    slots: list[AvailableSlotResponse]
