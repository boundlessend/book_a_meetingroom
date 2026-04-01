from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import FastAPI, Query, status

from app.handlers import register_exception_handlers
from app.schemas import (
    AvailableSlotResponse,
    AvailableSlotsResponse,
    BookingCreateRequest,
    BookingResponse,
    ErrorResponse,
)
from app.service import BookingService


def error_response_doc(
    description: str, example: dict[str, Any] | None = None
) -> dict[str, Any]:
    """собирает описание ошибки для openapi"""
    response: dict[str, Any] = {
        "model": ErrorResponse,
        "description": description,
    }
    if example is not None:
        response["content"] = {"application/json": {"example": example}}
    return response


VALIDATION_ERROR_DOC = error_response_doc(
    "ошибка валидации запроса",
    example={
        "error": {
            "code": "validation_error",
            "message": "запрос не прошел валидацию",
            "details": [
                {
                    "type": "greater_than_equal",
                    "loc": ["body", "room_id"],
                    "msg": "значение должно быть больше либо равно 1",
                    "input": 0,
                    "ctx": {"ge": 1},
                }
            ],
        }
    },
)
ROOM_NOT_FOUND_DOC = error_response_doc(
    "комната с указанным id не найдена",
    example={
        "error": {
            "code": "room_not_found",
            "message": "комната с id=999 не найдена",
            "details": {"room_id": 999},
        }
    },
)
BOOKING_NOT_FOUND_DOC = error_response_doc(
    "бронирование с указанным id не найдено",
    example={
        "error": {
            "code": "booking_not_found",
            "message": "бронирование с id=999 не найдено",
            "details": {"booking_id": 999},
        }
    },
)
BOOKING_CONFLICT_DOC = error_response_doc(
    "запрошенное время пересекается с активным бронированием",
    example={
        "error": {
            "code": "booking_conflict",
            "message": "время бронирования пересекается с активным бронированием",
            "details": {
                "conflicting_booking_id": 1,
                "room_id": 1,
                "start_at": "2026-04-01T10:30:00",
                "end_at": "2026-04-01T11:30:00",
            },
        }
    },
)
BOOKING_ALREADY_CANCELLED_DOC = error_response_doc(
    "бронирование уже отменено",
    example={
        "error": {
            "code": "booking_already_cancelled",
            "message": "бронирование с id=1 уже отменено",
            "details": {"booking_id": 1},
        }
    },
)


def create_app() -> FastAPI:
    """создает и настраивает приложение fastapi"""
    app = FastAPI(title="сервис бронирования переговорных")
    app.state.booking_service = BookingService()
    register_exception_handlers(app)

    @app.post(
        "/bookings",
        response_model=BookingResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            404: ROOM_NOT_FOUND_DOC,
            409: BOOKING_CONFLICT_DOC,
            422: VALIDATION_ERROR_DOC,
        },
    )
    def create_booking(payload: BookingCreateRequest) -> BookingResponse:
        """создает бронирование для существующей комнаты"""
        booking = app.state.booking_service.create_booking(
            room_id=payload.room_id,
            title=payload.title,
            start_at=payload.start_at,
            end_at=payload.end_at,
        )
        return BookingResponse.model_validate(booking, from_attributes=True)

    @app.get(
        "/bookings/{booking_id}",
        response_model=BookingResponse,
        responses={404: BOOKING_NOT_FOUND_DOC, 422: VALIDATION_ERROR_DOC},
    )
    def get_booking(booking_id: int) -> BookingResponse:
        """возвращает одно бронирование по id"""
        booking = app.state.booking_service.get_booking(booking_id)
        return BookingResponse.model_validate(booking, from_attributes=True)

    @app.get(
        "/bookings",
        response_model=list[BookingResponse],
        responses={404: ROOM_NOT_FOUND_DOC, 422: VALIDATION_ERROR_DOC},
    )
    def list_bookings(
        room_id: int | None = Query(default=None, ge=1),
        date: date | None = Query(default=None),
    ) -> list[BookingResponse]:
        """возвращает список бронирований с необязательными фильтрами"""
        bookings = app.state.booking_service.list_bookings(
            room_id=room_id,
            day=date,
        )
        return [
            BookingResponse.model_validate(item, from_attributes=True)
            for item in bookings
        ]

    @app.delete(
        "/bookings/{booking_id}",
        response_model=BookingResponse,
        responses={
            404: BOOKING_NOT_FOUND_DOC,
            409: BOOKING_ALREADY_CANCELLED_DOC,
            422: VALIDATION_ERROR_DOC,
        },
    )
    def cancel_booking(booking_id: int) -> BookingResponse:
        """отменяет существующее бронирование"""
        booking = app.state.booking_service.cancel_booking(booking_id)
        return BookingResponse.model_validate(booking, from_attributes=True)

    @app.get(
        "/rooms/{room_id}/available-slots",
        response_model=AvailableSlotsResponse,
        responses={404: ROOM_NOT_FOUND_DOC, 422: VALIDATION_ERROR_DOC},
    )
    def get_available_slots(
        room_id: int,
        date: date = Query(),
    ) -> AvailableSlotsResponse:
        """возвращает свободные интервалы комнаты на выбранную дату"""
        slots = app.state.booking_service.get_available_slots(
            room_id=room_id, day=date
        )
        return AvailableSlotsResponse(
            room_id=room_id,
            date=date,
            slots=[
                AvailableSlotResponse(start_at=start_at, end_at=end_at)
                for start_at, end_at in slots
            ],
        )

    return app


app = create_app()
