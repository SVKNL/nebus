# Асинхронный сервис процессинга платежей

Микросервис принимает платежи по HTTP, **гарантированно** публикует событие в RabbitMQ через **Outbox**, обрабатывает его одним consumer'ом (эмуляция платёжного шлюза 2–5 секунд, 90% success / 10% fail) и уведомляет клиента **webhook'ом**.

Стек: **FastAPI + Pydantic v2**, **SQLAlchemy 2.0 async**, **PostgreSQL**, **RabbitMQ (FastStream)**, **Alembic**, **Docker Compose**.

## Архитектура

```
Клиент
  │  POST /api/v1/payments  (X-API-Key, Idempotency-Key)
  ▼
API (FastAPI)
  │  одна транзакция: INSERT payments + INSERT outbox
  ▼
Таблица outbox
  │  фоновый OutboxPublisher в процессе API (FOR UPDATE SKIP LOCKED)
  ▼
Exchange payments  →  очередь payments.new
  │
  │  ошибка обработки → очередь payments.retry (TTL 1s/2s/4s) → снова payments.new
  │  после 3 попыток  → exchange payments.dlx → очередь payments.new.dlq
  ▼
Consumer (FastStream)
  │  эмуляция шлюза → UPDATE status → HTTP webhook (3 попытки, exponential backoff)
  ▼
Клиентский webhook_url
```

### Outbox

Событие не публикуется в брокер внутри HTTP-запроса. Сначала оно попадает в таблицу `outbox` **в той же транзакции**, что и платёж. Если RabbitMQ лежал, HTTP всё равно вернёт 202, а publisher догонит очередь, когда брокер оживёт.

### Идемпотентность

Заголовок `Idempotency-Key` уникален в БД.

- тот же ключ и то же тело → исходный платёж, снова **202**;
- тот же ключ и другое тело → **409 Conflict**.

Consumer идемпотентен: повторная доставка не вызывает шлюз повторно, если статус уже терминальный; webhook не дублируется после успешной доставки (`webhook_sent_at`).

### Retry и DLQ

| Слой | Политика |
| --- | --- |
| Webhook | 3 попытки, задержки 1с → 2с → 4с (tenacity) |
| Сообщение очереди | 3 попытки; между ними delayed retry через TTL-очередь |
| После 3-й ошибки | сообщение в `payments.new.dlq` |

## Запуск

Нужны Docker и Docker Compose v2.

```bash
cp .env.example .env   # необязательно: есть значения по умолчанию
docker compose up --build
```

Сервисы:

| Сервис | Адрес |
| --- | --- |
| API, Swagger | http://localhost:8000/docs |
| Health | http://localhost:8000/health |
| RabbitMQ UI | http://localhost:15672 (guest/guest) |
| PostgreSQL | localhost:5432, user/password/db: `payments` |

Миграции Alembic выполняются при старте контейнеров `api` и `consumer`.

## Примеры API

Ключ по умолчанию: `test-api-key-change-me`. Смените `API_KEY` в окружении перед боем.

### Создать платёж (202 Accepted)

```bash
curl -i -X POST http://localhost:8000/api/v1/payments \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-api-key-change-me" \
  -H "Idempotency-Key: order-42-try-1" \
  -d "{
    \"amount\": \"100.50\",
    \"currency\": \"RUB\",
    \"description\": \"Оплата заказа 42\",
    \"metadata\": {\"order_id\": \"42\"},
    \"webhook_url\": \"https://webhook.site/your-id\"
  }"
```

Ответ:

```json
{
  "payment_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "pending",
  "created_at": "2026-10-06T12:00:00+00:00"
}
```

Для локальной проверки webhook удобен [https://webhook.site](https://webhook.site) или `https://httpbin.org/post`.

### Получить платёж

```bash
curl -X GET http://localhost:8000/api/v1/payments/<payment_id> \
  -H "X-API-Key: test-api-key-change-me"
```

Через несколько секунд `status` станет `succeeded` или `failed`, появятся `processed_at` и `webhook_sent_at`.

### Ошибки

| Код | Когда |
| --- | --- |
| 401 | нет или неверный `X-API-Key` |
| 404 | неизвестный `payment_id` |
| 409 | `Idempotency-Key` уже занят другим телом |
| 422 | нет `Idempotency-Key` или невалидное тело |

## Локальная разработка без Docker (API)

PostgreSQL и RabbitMQ всё равно нужны (можно поднять только их из compose).

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
set DATABASE_URL=postgresql+asyncpg://payments:payments@localhost:5432/payments
set RABBITMQ_URL=amqp://guest:guest@localhost:5672/
set API_KEY=test-api-key-change-me
alembic upgrade head
uvicorn app.main:app --reload
faststream run app.consumer.main:app
```

## Ruff

```bash
ruff check app tests
ruff format app tests
ruff check app tests --output-format json -o ruff-report.json
```

Конфигурация — в `pyproject.toml` (py312, линия 100, правила E/F/I/N/UP/B/S/RUF/ASYNC и др.).

## Тесты

```bash
pytest --cov=app --cov-report=xml --cov-report=term-missing
```

CI (GitHub Actions) гоняет Ruff и pytest на каждый push.

## SonarQube

1. Поднять сервер (первый старт 1–2 минуты):

   ```bash
   docker compose --profile sonar up -d sonarqube
   ```

2. Открыть http://localhost:9000 (логин/пароль по умолчанию `admin`/`admin`), создать проект `nebus-payments` и токен.

3. Прогнать анализ (нужны `coverage.xml` и `ruff-report.json`):

   ```bash
   pytest --cov=app --cov-report=xml
   ruff check app tests --output-format json -o ruff-report.json
   docker compose --profile sonar run --rm -e SONAR_TOKEN=<token> sonar-scanner
   ```

Настройки проекта — `sonar-project.properties` (`sonar.sources=app`, Python 3.12, отчёты coverage и Ruff).

## Структура репозитория

```
app/
  api/v1/          HTTP эндпоинты
  consumer/        FastStream subscriber + retry/DLQ
  messaging/       broker, очереди, политика попыток
  models/          Payment, OutboxEvent
  services/        create/get, outbox, gateway, webhook, processor
alembic/versions/  миграция payments + outbox
tests/             юнит-тесты без живых Postgres/Rabbit
```

## Таблицы

- `payments` — платёж: сумма Decimal, валюта RUB/USD/EUR, описание, JSON metadata, статус, idempotency key, webhook URL, даты создания/обработки, `webhook_sent_at`.
- `outbox` — событие `payments.new`, payload JSON, `published_at`, счётчик попыток публикации.
