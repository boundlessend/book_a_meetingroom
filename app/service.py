from __future__ import annotations

from datetime import date, datetime, time, timedelta
from itertools import count
from threading import RLock

from app.errors import AppError
from app.models import Booking, BookingStatus, Room


class BookingService:
    """сервис бронирования переговорных"""

    def __init__(self) -> None:
        self._rooms: dict[int, Room] = {
            room.id: room
            for room in (
                Room(id=1, name="Biba"),
                Room(id=2, name="Boba"),
                Room(id=3, name="Luntik"),
            )
        }
        self._bookings: dict[int, Booking] = {}
        self._id_sequence = count(1)
        self._lock = RLock()

    def create_booking(
        self,
        *,
        room_id: int,
        title: str,
        start_at: datetime,
        end_at: datetime,
    ) -> Booking:
        """создает бронирование, если комната существует и слот свободен"""
        self._get_room_or_raise(room_id)
        with self._lock:
            conflicting_booking = self._find_conflicting_booking(
                room_id=room_id,
                start_at=start_at,
                end_at=end_at,
            )
            if conflicting_booking is not None:
                raise AppError(
                    code="booking_conflict",
                    message="booking time intersects with an active booking",
                    status_code=409,
                    details={
                        "conflicting_booking_id": conflicting_booking.id,
                        "room_id": room_id,
                        "start_at": start_at.isoformat(),
                        "end_at": end_at.isoformat(),
                    },
                )

            booking = Booking(
                id=next(self._id_sequence),
                room_id=room_id,
                title=title,
                start_at=start_at,
                end_at=end_at,
                status=BookingStatus.ACTIVE,
            )
            self._bookings[booking.id] = booking
            return booking

    def get_booking(self, booking_id: int) -> Booking:
        """возвращает бронирование по id"""
        with self._lock:
            booking = self._bookings.get(booking_id)
            if booking is None:
                raise AppError(
                    code="booking_not_found",
                    message=f"booking with id={booking_id} was not found",
                    status_code=404,
                    details={"booking_id": booking_id},
                )
            return booking

    def list_bookings(
        self, *, room_id: int | None = None, day: date | None = None
    ) -> list[Booking]:
        """возвращает список бронирований с необязательной фильтрацией"""
        if room_id is not None:
            self._get_room_or_raise(room_id)

        day_start: datetime | None = None
        day_end: datetime | None = None
        if day is not None:
            day_start, day_end = self._day_bounds(day)

        with self._lock:
            bookings = list(self._bookings.values())
            if room_id is not None:
                bookings = [
                    booking
                    for booking in bookings
                    if booking.room_id == room_id
                ]
            if day_start is not None and day_end is not None:
                bookings = [
                    booking
                    for booking in bookings
                    if self._intervals_overlap(
                        booking.start_at,
                        booking.end_at,
                        day_start,
                        day_end,
                    )
                ]
            bookings.sort(key=lambda item: (item.start_at, item.id))
            return bookings

    def cancel_booking(self, booking_id: int) -> Booking:
        """отменяет существующее бронирование"""
        with self._lock:
            booking = self._bookings.get(booking_id)
            if booking is None:
                raise AppError(
                    code="booking_not_found",
                    message=f"booking with id={booking_id} was not found",
                    status_code=404,
                    details={"booking_id": booking_id},
                )
            if booking.status == BookingStatus.CANCELLED:
                raise AppError(
                    code="booking_already_cancelled",
                    message=f"booking with id={booking_id} is already cancelled",
                    status_code=409,
                    details={"booking_id": booking_id},
                )
            booking.status = BookingStatus.CANCELLED
            return booking

    def get_available_slots(
        self, *, room_id: int, day: date
    ) -> list[tuple[datetime, datetime]]:
        """возвращает свободные интервалы комнаты внутри дня"""
        self._get_room_or_raise(room_id)
        day_start, day_end = self._day_bounds(day)
        with self._lock:
            busy_intervals = [
                (
                    max(booking.start_at, day_start),
                    min(booking.end_at, day_end),
                )
                for booking in self._bookings.values()
                if booking.room_id == room_id
                and booking.status == BookingStatus.ACTIVE
                and self._intervals_overlap(
                    booking.start_at, booking.end_at, day_start, day_end
                )
            ]
            busy_intervals.sort(key=lambda item: item[0])

        slots: list[tuple[datetime, datetime]] = []
        cursor = day_start
        for busy_start, busy_end in busy_intervals:
            if cursor < busy_start:
                slots.append((cursor, busy_start))
            if cursor < busy_end:
                cursor = busy_end
        if cursor < day_end:
            slots.append((cursor, day_end))
        return slots

    def _get_room_or_raise(self, room_id: int) -> Room:
        room = self._rooms.get(room_id)
        if room is None:
            raise AppError(
                code="room_not_found",
                message=f"room with id={room_id} was not found",
                status_code=404,
                details={"room_id": room_id},
            )
        return room

    def _find_conflicting_booking(
        self,
        *,
        room_id: int,
        start_at: datetime,
        end_at: datetime,
    ) -> Booking | None:
        for booking in self._bookings.values():
            if booking.room_id != room_id:
                continue
            if booking.status != BookingStatus.ACTIVE:
                continue
            if self._intervals_overlap(
                start_at, end_at, booking.start_at, booking.end_at
            ):
                return booking
        return None

    @staticmethod
    def _intervals_overlap(
        start_at: datetime,
        end_at: datetime,
        other_start_at: datetime,
        other_end_at: datetime,
    ) -> bool:
        return start_at < other_end_at and other_start_at < end_at

    @staticmethod
    def _day_bounds(day: date) -> tuple[datetime, datetime]:
        return datetime.combine(day, time.min), datetime.combine(
            day, time.min
        ) + timedelta(days=1)
