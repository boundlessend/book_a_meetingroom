from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class BookingStatus(str, Enum):
    """статусы бронирования"""

    ACTIVE = "active"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Room:
    """комната для бронирования"""

    id: int
    name: str


@dataclass()
class Booking:
    """модель бронирования"""

    id: int
    room_id: int
    title: str
    start_at: datetime
    end_at: datetime
    status: BookingStatus
