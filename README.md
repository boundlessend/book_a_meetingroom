# book-a-meeting-room

## что есть

- создание брони
- чтение одной брони
- список брони с необязательными фильтрами по комнате и дате
- отмена брони
- список доступных слотов по комнате и дате;
- единый формат доменных и валидационных ошибок
- `pytest`-тесты на happy path и негативные сценарии

## что внутри

- Python
- FastAPI
- Pydantic
- uvicorn
- pytest
- in-memory хранение на стандартной библиотеке Python

## структура проекта

```text
app/
  errors.py
  handlers.py
  main.py
  models.py
  schemas.py
  service.py
tests/
  test_bookings.py
README.md
requirements.txt
```

## запуск

### 1. создать и активировать виртуальное окружение

macOS / linux:

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. установить зависимости

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. поднять сервис

```bash
uvicorn app.main:app --reload
```

сервис будет доступен по адресу:

```text
http://127.0.0.1:8000
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

## запуск тестов

```bash
pytest
```

## формат ошибок

все доменные и валидационные ошибки возвращаются в одном формате:

```json
{
  "error": {
    "code": "booking_conflict",
    "message": "booking time intersects with an active booking",
    "details": {
      "conflicting_booking_id": 1,
      "room_id": 1,
      "start_at": "2026-04-01T10:30:00",
      "end_at": "2026-04-01T11:30:00"
    }
  }
}
```

## комнаты

в сервисе заранее заведены переговорки:

- `1` — Biba
- `2` — Boba
- `3` — Luntik

во всех запросах используется нормальная связь по `room_id` как по целочисленному идентификатору комнаты

## API

### 1. создать бронь

`POST /bookings`

пример тела:

```json
{
  "room_id": 1,
  "title": "Backend sync",
  "start_at": "2026-04-01T10:00:00",
  "end_at": "2026-04-01T11:00:00"
}
```

пример ответа:

```json
{
  "id": 1,
  "room_id": 1,
  "title": "Backend sync",
  "start_at": "2026-04-01T10:00:00",
  "end_at": "2026-04-01T11:00:00",
  "status": "active"
}
```

### 2. получить одну бронь

`GET /bookings/{booking_id}`

### 3. получить список броней

`GET /bookings`

поддерживаются необязательные фильтры:

- `room_id`
- `date`

примеры:

- `GET /bookings`
- `GET /bookings?room_id=1`
- `GET /bookings?date=2026-04-01`
- `GET /bookings?room_id=1&date=2026-04-01`

список всегда сортируется по `start_at`

### 4. отменить бронь

`DELETE /bookings/{booking_id}`

возвращает обновленную бронь со статусом `cancelled`

### 5. получить доступные слоты по комнате и дате

`GET /rooms/{room_id}/available-slots?date=2026-04-01`

возвращаются свободные интервалы внутри выбранной даты от `00:00:00` до `24:00:00`

## для ручной проверки

### успешное создание брони

```bash
curl -X POST http://127.0.0.1:8000/bookings \
  -H "Content-Type: application/json" \
  -d '{
    "room_id": 1,
    "title": "Daily sync",
    "start_at": "2026-04-01T10:00:00",
    "end_at": "2026-04-01T11:00:00"
  }'
```

лжидание: `201 Created`, в ответе есть `id` и `status=active`

### запрет пересечения интервалов

после прошлого запроса:

```bash
curl -X POST http://127.0.0.1:8000/bookings \
  -H "Content-Type: application/json" \
  -d '{
    "room_id": 1,
    "title": "Conflict meeting",
    "start_at": "2026-04-01T10:30:00",
    "end_at": "2026-04-01T11:30:00"
  }'
```

ожидание: `409 Conflict`, код ошибки `booking_conflict`

### соседние интервалы допустимы

```bash
curl -X POST http://127.0.0.1:8000/bookings \
  -H "Content-Type: application/json" \
  -d '{
    "room_id": 1,
    "title": "Next meeting",
    "start_at": "2026-04-01T11:00:00",
    "end_at": "2026-04-01T12:00:00"
  }'
```

ожидание: `201 Created`, т.к. первая бронь закончилась ровно в момент начала второй

### список брони без фильтров

```bash
curl "http://127.0.0.1:8000/bookings"
```

ожидание: все брони, отсортированные по `start_at`

### список брони по комнате и дате

```bash
curl "http://127.0.0.1:8000/bookings?room_id=1&date=2026-04-01"
```

ожидание: брони комнаты `1`, которые пересекают дату `2026-04-01`, отсортированные по `start_at`

### отмена брони

```bash
curl -X DELETE http://127.0.0.1:8000/bookings/1
```

ожидание: `200 OK`, в ответе у брони статус `cancelled`

### освобождение слота после отмены

после сценария отмены брони:

```bash
curl -X POST http://127.0.0.1:8000/bookings \
  -H "Content-Type: application/json" \
  -d '{
    "room_id": 1,
    "title": "Rebooked slot",
    "start_at": "2026-04-01T10:00:00",
    "end_at": "2026-04-01T11:00:00"
  }'
```

ожидание: `201 Created`, потому что отмененная бронь больше не блокирует слот

### список доступных слотов

```bash
curl "http://127.0.0.1:8000/rooms/1/available-slots?date=2026-04-01"
```

ожидание: свободные интервалы внутри выбранной даты, не занятые активными бронями

## допущения

1. в сервисе есть заранее заданный in-memory справочник комнат, чтобы `room_id` был связью на сущность, а не произвольной строкой
2. сервис принимает **naive datetime** в формате ISO 8601 без timezone, например `2026-04-01T10:00:00`
3. доступные слоты считаются внутри выбранной даты как интервалы в пределах `[00:00, 24:00)`
4. в списке броней возвращаются все брони, подходящие под выбранные фильтры, включая отмененные: это позволяет видеть текущий статус в одном месте
5. повторная отмена уже отмененной брони считается ошибкой `409`, потому что состояние уже изменено ранее

## как определяется конфликт интервалов

используется правило полуинтервалов:

```text
[start_at, end_at)
```

две активные брони конфликтуют, если одновременно выполняется:

```text
new_start < existing_end AND existing_start < new_end
```
