from fastapi.testclient import TestClient

from app.main import create_app


def build_client() -> TestClient:
    return TestClient(create_app())


def test_creates_booking_and_prevents_overlap_in_same_room() -> None:
    client = build_client()

    first_response = client.post(
        "/bookings",
        json={
            "room_id": 1,
            "title": "Daily sync",
            "start_at": "2026-04-01T10:00:00",
            "end_at": "2026-04-01T11:00:00",
        },
    )
    assert first_response.status_code == 201

    second_response = client.post(
        "/bookings",
        json={
            "room_id": 1,
            "title": "Retro",
            "start_at": "2026-04-01T10:30:00",
            "end_at": "2026-04-01T11:30:00",
        },
    )

    assert second_response.status_code == 409
    assert second_response.json()["error"]["code"] == "booking_conflict"


def test_allows_adjacent_bookings() -> None:
    client = build_client()

    first_response = client.post(
        "/bookings",
        json={
            "room_id": 1,
            "title": "Morning",
            "start_at": "2026-04-01T09:00:00",
            "end_at": "2026-04-01T10:00:00",
        },
    )
    assert first_response.status_code == 201

    second_response = client.post(
        "/bookings",
        json={
            "room_id": 1,
            "title": "Next meeting",
            "start_at": "2026-04-01T10:00:00",
            "end_at": "2026-04-01T11:00:00",
        },
    )

    assert second_response.status_code == 201


def test_cancelled_booking_does_not_block_new_booking() -> None:
    client = build_client()

    create_response = client.post(
        "/bookings",
        json={
            "room_id": 1,
            "title": "To cancel",
            "start_at": "2026-04-01T13:00:00",
            "end_at": "2026-04-01T14:00:00",
        },
    )
    assert create_response.status_code == 201

    cancel_response = client.delete("/bookings/1")
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"

    recreate_response = client.post(
        "/bookings",
        json={
            "room_id": 1,
            "title": "Replacement",
            "start_at": "2026-04-01T13:00:00",
            "end_at": "2026-04-01T14:00:00",
        },
    )
    assert recreate_response.status_code == 201


def test_returns_sorted_bookings_for_optional_filters() -> None:
    client = build_client()

    for room_id, title, start_at, end_at in [
        (2, "Late", "2026-04-02T15:00:00", "2026-04-02T16:00:00"),
        (2, "Early", "2026-04-02T09:00:00", "2026-04-02T10:00:00"),
        (3, "Other room", "2026-04-02T11:00:00", "2026-04-02T12:00:00"),
    ]:
        response = client.post(
            "/bookings",
            json={
                "room_id": room_id,
                "title": title,
                "start_at": start_at,
                "end_at": end_at,
            },
        )
        assert response.status_code == 201

    all_response = client.get("/bookings")
    assert all_response.status_code == 200
    assert [item["title"] for item in all_response.json()] == [
        "Early",
        "Other room",
        "Late",
    ]

    filtered_response = client.get(
        "/bookings", params={"room_id": 2, "date": "2026-04-02"}
    )
    assert filtered_response.status_code == 200
    assert [item["title"] for item in filtered_response.json()] == [
        "Early",
        "Late",
    ]


def test_available_slots_are_built_inside_selected_day() -> None:
    client = build_client()

    for payload in [
        {
            "room_id": 1,
            "title": "First",
            "start_at": "2026-04-03T09:00:00",
            "end_at": "2026-04-03T10:00:00",
        },
        {
            "room_id": 1,
            "title": "Second",
            "start_at": "2026-04-03T12:00:00",
            "end_at": "2026-04-03T13:30:00",
        },
    ]:
        response = client.post("/bookings", json=payload)
        assert response.status_code == 201

    slots_response = client.get(
        "/rooms/1/available-slots", params={"date": "2026-04-03"}
    )
    assert slots_response.status_code == 200

    slots = slots_response.json()["slots"]
    assert slots == [
        {"start_at": "2026-04-03T00:00:00", "end_at": "2026-04-03T09:00:00"},
        {"start_at": "2026-04-03T10:00:00", "end_at": "2026-04-03T12:00:00"},
        {"start_at": "2026-04-03T13:30:00", "end_at": "2026-04-04T00:00:00"},
    ]


def test_returns_clear_errors_for_invalid_input_and_missing_entities() -> None:
    client = build_client()

    invalid_interval_response = client.post(
        "/bookings",
        json={
            "room_id": 1,
            "title": "Broken",
            "start_at": "2026-04-01T11:00:00",
            "end_at": "2026-04-01T10:00:00",
        },
    )
    assert invalid_interval_response.status_code == 422
    assert (
        invalid_interval_response.json()["error"]["code"] == "validation_error"
    )

    invalid_datetime_response = client.post(
        "/bookings",
        json={
            "room_id": 1,
            "title": "Broken datetime",
            "start_at": "not-a-datetime",
            "end_at": "2026-04-01T10:00:00",
        },
    )
    assert invalid_datetime_response.status_code == 422

    missing_room_response = client.post(
        "/bookings",
        json={
            "room_id": 999,
            "title": "Unknown room",
            "start_at": "2026-04-01T09:00:00",
            "end_at": "2026-04-01T10:00:00",
        },
    )
    assert missing_room_response.status_code == 404
    assert missing_room_response.json()["error"]["code"] == "room_not_found"

    missing_booking_response = client.delete("/bookings/999")
    assert missing_booking_response.status_code == 404
    assert (
        missing_booking_response.json()["error"]["code"] == "booking_not_found"
    )


def test_openapi_documents_custom_error_schema() -> None:
    client = build_client()

    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200

    booking_post = openapi.json()["paths"]["/bookings"]["post"]
    validation_schema = booking_post["responses"]["422"]["content"][
        "application/json"
    ]["schema"]
    assert validation_schema["$ref"].endswith("/ErrorResponse")
