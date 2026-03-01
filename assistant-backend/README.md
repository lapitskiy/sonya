# Personal Voice Assistant Backend

DDD-based backend для персонального голосового ассистента с напоминаниями, geo-триггерами и долгосрочной памятью.

## Архитектура

Проект следует принципам Domain-Driven Design (DDD) с четким разделением слоев:

```
assistant/
├─ apps/                # Entrypoints
│  ├─ api/              # FastAPI application
│  └─ worker/           # Background worker loops
│
├─ domain/              # PURE DOMAIN (NO IO)
│  ├─ reminder/         # Reminder domain
│  │  ├─ entities.py    # Domain entities
│  │  ├─ value_objects.py
│  │  ├─ rules.py       # Domain rules
│  │  ├─ intents.py     # Domain intents
│  │  └─ services.py    # Domain services
│  │
│  ├─ memory/           # Memory domain
│  │  ├─ entities.py
│  │  ├─ policies.py
│  │  └─ summarizer.py
│  │
│  └─ user/             # User domain
│     ├─ entities.py
│     └─ preferences.py
│
├─ use_cases/           # APPLICATION LAYER
│  ├─ create_reminder.py
│  ├─ handle_command.py
│  ├─ evaluate_geo.py
│  └─ notify_user.py
│
├─ infrastructure/      # IO + frameworks
│  ├─ db/
│  │  ├─ models.py      # SQLAlchemy models
│  │  ├─ repositories.py
│  │  └─ migrations/
│  │
│  ├─ llm/
│  │  ├─ client.py
│  │  ├─ prompt_templates.py
│  │  └─ parsers.py
│  │
│  ├─ notifications/
│  │  └─ push_gateway.py
│  │
│  └─ geo/
│     └─ geofence.py
│
└─ contracts/           # AI-friendly contracts
   ├─ intents.py        # JSON schemas для LLM
   ├─ commands.py
   └─ events.py
```

## Принципы

### Domain Layer (PURE)
- ❌ НЕТ импортов из FastAPI, SQLAlchemy, LLM клиентов
- ✅ Только Python, dataclasses, enums
- ✅ Чистая бизнес-логика

### Use Cases Layer
- Оркестрация use-case
- Вызывает domain + repositories
- 1 файл = 1 use case

### Infrastructure Layer
- Заменяемые реализации
- Изолированы от domain
- Работа с БД, LLM, внешними сервисами

### Contracts Layer
- Явные JSON схемы для LLM
- Стабильные типы
- Структурированный вывод от AI

## Flow

```
Voice text
  ↓
API Controller
  ↓
HandleCommand use-case
  ↓
LLM → Intent (JSON)
  ↓
Domain validation
  ↓
CreateReminder use-case
  ↓
Repository.save()
```

## Memory Model

| Type | Where |
|------|-------|
| Short-term | Redis / RAM (optional) |
| Episodic | Postgres |
| Semantic | Summaries |
| Preferences | Domain.User |

**Memory ≠ chat history**

## Разработка

### Создание миграций Alembic

```bash
docker exec -it assistant_api alembic -c utils_global/alembic/alembic.ini revision --autogenerate -m "<msg>"
docker exec -it assistant_api alembic -c utils_global/alembic/alembic.ini upgrade head
```

### Правила для Cursor

- ✅ Разрешено: новые use-cases, domain rules, repositories, DTOs, тесты
- ❌ Запрещено: прямые записи в БД из API, cross-layer imports, "магическая" LLM логика

## MVP Tasks

- [x] Create Reminder domain entity
- [x] Create Trigger value object
- [x] Define ReminderIntent contract
- [x] Implement CreateReminder use-case
- [x] Implement Postgres repository
- [x] Worker loop structure (apps/worker/main.py)
- [ ] API endpoint /command (TODO: integrate with FastAPI)
- [ ] Complete LLM client implementation
- [ ] Complete Push gateway implementation

## Структура проекта

Все модули следуют DDD принципам:

- **domain/** — чистая бизнес-логика, без IO
- **use_cases/** — оркестрация, один файл = один use case
- **infrastructure/** — реализация IO (БД, LLM, уведомления)
- **contracts/** — явные контракты для LLM (JSON schemas)
- **apps/** — точки входа (API, worker)
