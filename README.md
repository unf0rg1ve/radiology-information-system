# RIS MVP — Радиологическая информационная система

**Версия:** 1.1.0 | **Дата:** 2026-06-20 | **Рынок:** Республика Казахстан

## Что это?

RIS MVP — полнофункциональная радиологическая информационная система (Radiology Information System), разработанная в соответствии с требованиями законодательства Республики Казахстан (Приказ МЗ РК от 25.01.2011 № 30, приказ МЗ РК от 01.07.2020, приказ МЗ РК от 10.02.2023 № 47).

Система автоматизирует рабочие процессы диагностического центра: от регистрации пациента до выдачи подписанного заключения с возможностью интеграции с Национальным реестром здоровья и СЭМД.

## Архитектура

```
┌──────────────────────────────────────────────────────────────┐
│                       FRONTEND                                │
│  React 19 + TypeScript + Ant Design + Zustand + React Router  │
│  nginx (reverse proxy) → :3000                                │
└─────────────────────┬────────────────────────────────────────┘
                      │ HTTP / REST / JWT / WebSocket
                      ▼
┌──────────────────────────────────────────────────────────────┐
│                       BACKEND                                 │
│  FastAPI + SQLAlchemy (async) + Pydantic + Alembic           │
│  PostgreSQL 16                                                │
└─────────────────────┬────────────────────────────────────────┘
                      │ DICOM Web / WADO-RS
                      ▼
┌──────────────────────────────────────────────────────────────┐
│                    DICOM PROXY                                 │
│  aiohttp (Python) → :8043 → Native Orthanc → :8042           │
└──────────────────────────────────────────────────────────────┘
```

## Технологический стек

### Backend
| Компонент | Технология | Назначение |
|-----------|-----------|------------|
| Framework | FastAPI | ASGI web framework |
| ORM | SQLAlchemy (async) | Работа с БД |
| Migrations | Alembic | Миграции схемы |
| База данных | PostgreSQL 16 | Основное хранилище |
| DICOM | Native Orthanc (service) | DICOM-сервер (Windows service) |
| Proxy | aiohttp (Python) | Прокси для DICOM-запросов |
| Auth | python-jose + passlib | JWT + Argon2 |
| PDF | WeasyPrint | Генерация заключений и направлений |
| WebSocket | FastAPI WebSocket | Real-time уведомления |

### Frontend
| Компонент | Технология | Назначение |
|-----------|-----------|------------|
| Framework | React 19 | UI библиотека |
| Language | TypeScript | Типизация |
| UI Kit | Ant Design 5 | Компоненты |
| Router | React Router 7 | Навигация |
| State | Zustand | Управление состоянием |
| HTTP | Axios | API клиент |
| i18n | i18next | Интернационализация (RU/KZ) |
| DICOM Viewer | Stone Web Viewer (iframe) | Просмотр снимков |
| Build | Vite 6 | Сборка |

## Быстрый запуск (Windows)

### Автоматический запуск (рекомендуется)

1. Дважды кликните по `start-server.bat`
2. Скрипт автоматически:
   - Определит ваш LAN IP-адрес
   - Запишет его в `.env`
   - Запустит Docker Compose (PostgreSQL, Backend, Frontend, Nginx)
   - Запустит DICOM-прокси (aiohttp) на порту 8043
   - Откроет приложение в браузере

```
Frontend:     http://<ваш_IP>:3000
Backend API:  http://<ваш_IP>:8000/docs
Proxy:        http://<ваш_IP>:8043
```

### Ручной запуск

```bash
# 1. Запустить Docker Compose
docker-compose up -d

# 2. Запустить DICOM-прокси
cscript start-proxy.vbs

# 3. Открыть приложение
# Frontend: http://localhost:3000
# Backend: http://localhost:8000/docs
```

### Доступ по умолчанию

| Сервис | URL | Логин / Пароль |
|--------|-----|----------------|
| Frontend | http://localhost:3000 | admin / admin123 |
| Backend API | http://localhost:8000 | — |
| Swagger UI | http://localhost:8000/docs | — |
| PostgreSQL | localhost:5432 | ris / ris |

## Роли и права доступа (RBAC)

| Роль | Доступ |
|------|--------|
| **Регистратор** (REGISTRAR) | Пациенты, направления, расписание |
| **Технолог** (TECHNOLOGIST) | Worklist, QC, снимки, привязка студий |
| **Радиолог** (RADIOLOGIST) | Заключения, подписание, описание |
| **Заведующий** (HEAD) | Всё + статистика, выдача заключений |
| **Направитель** (REFERRER) | Просмотр заключений, CITO-уведомления |
| **Администратор** (ADMIN) | Полный доступ + управление пользователями |

## Модули системы

### Регистратура
- Картотека пациентов с ИИН (поиск, создание, редактирование)
- Создание направлений с выбором услуги, диагноза МКБ-10
- Автоматический генератор Accession Number
- Тип финансирования: ГОБМП / ОСМС / Платно

### Расписание
- Календарь записи на аппараты
- Управление слотами по устройствам и датам
- Привязка направлений к слотам

### Worklist (технолог)
- Рабочая лента с фильтрами по статусу, дате, приоритету
- Отметка прибытия пациента
- Контроль качества (QC): ACCEPTED / RETAKE
- Привязка DICOM-студий к направлениям
- Несопоставленные исследования (unmatched) — очередь для ручного сопоставления

### Просмотр снимков (DICOM Viewer)
- Встроенный Stone Web Viewer через iframe
- Просмотр DICOM-исследований из Orthanc
- Интеграция в панель заключений

### Протоколирование (радиолог)
- Создание заключений на основе шаблонов
- Структурированные поля (описание, заключение, МКБ-10)
- Черновик → Подписание → Выдача
- ЭЦП-ready: SHA-256 хэш содержимого
- Критические находки (CITO) с оповещением направителя

### PDF-генерация
- Направление на исследование (с реквизитами организации)
- Медицинское заключение (с подписью врача)
- Реквизиты организации берутся из БД (Справочники → Реквизиты организации)
- Водяной знак «ЧЕРНОВИК» для черновиков
- Красный штамп «КРИТИЧЕСКАЯ НАХОДКА» при critical_finding

### Уведомления
- Реал-тайм уведомления через WebSocket
- Подробные описания действий:
  - Направление:atient, услуга, модальность, тело
  - Снимки: модальность, дата, привязка к направлению
  - Заключения: версия, врач, статус
  - CITO: критическая находка с ФИО радиолога
- Фильтрация по ролям (каждая роль видит только свои уведомления)
- Очистка уведомлений

### Администрирование
- Управление пользователями (роли, пароли)
- Аудит-лог всех действий
- Справочники: услуги, устройства, шаблоны протоколов, МКБ-10
- Реквизиты организации (для PDF)

### Международизация
- Двуязычный интерфейс: русский / казахский
- Локализованные даты (день недели, месяц на казахском)

## API Endpoints

### Аутентификация
| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/auth/login` | Вход (JWT) |
| GET | `/api/auth/me` | Текущий пользователь |

### Пациенты
| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/patients` | Список пациентов |
| POST | `/api/patients` | Создать пациента |
| PUT | `/api/patients/{id}` | Обновить пациента |

### Направления
| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/orders` | Список направлений |
| POST | `/api/orders` | Создать направление |
| PUT | `/api/orders/{id}/status` | Обновить статус |
| GET | `/api/orders/{id}/pdf` | PDF направления |
| GET | `/api/orders?without_study=true` | Направления без привязанных снимков |

### Заключения
| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/reports` | Список заключений |
| POST | `/api/reports` | Создать черновик |
| PUT | `/api/reports/{id}` | Редактировать |
| POST | `/api/reports/{id}/sign` | Подписать |
| POST | `/api/reports/{id}/issue` | Выдать |
| GET | `/api/reports/{id}/pdf` | PDF заключения |

### Worklist
| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/worklist` | Список на выполнение |
| POST | `/api/worklist/{id}/arrived` | Прибыл пациента |
| POST | `/api/worklist/{id}/in-progress` | Начать обследование |
| POST | `/api/worklist/{id}/qc` | QC контроль (ACCEPTED/RETAKE) |
| POST | `/api/worklist/{id}/retake` | Пересъёмка |
| GET | `/api/worklist/unmatched` | Несопоставленные исследования |
| POST | `/api/worklist/unmatched/{id}/resolve` | Привязать снимок к направлению |

### Уведомления
| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/notifications/list` | Список уведомлений |
| GET | `/api/notifications/cito` | CITO-уведомления |
| POST | `/api/notifications/clear` | Очистить уведомления |

### Расписание
| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/schedule/slots` | Слоты записи |
| POST | `/api/schedule/appointments` | Записать на слот |
| DELETE | `/api/schedule/appointments/{id}` | Отменить запись |

### Справочники
| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/refs/services` | Услуги (тарифы) |
| GET | `/api/refs/devices` | Аппараты |
| GET | `/api/refs/icd10` | Диагнозы МКБ-10 |
| GET | `/api/refs/protocol-templates` | Шаблоны протоколов |
| GET | `/api/refs/organization` | Реквизиты организации |
| PUT | `/api/refs/organization` | Обновить реквизиты |

### Администрирование
| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/admin/users` | Пользователи |
| POST | `/api/admin/users` | Создать пользователя |
| PUT | `/api/admin/users/{id}` | Обновить пользователя |
| GET | `/api/admin/audit` | Аудит-лог |

### Статистика
| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/stats/dashboard` | Дашборд |
| GET | `/api/stats/turnaround` | TAT-анализ |

## Архитектура DICOM

Система использует нативный Orthanc (Windows service) для хранения DICOM-данных. Для обхода ограничений `RemoteAccessAllowed: false` используется локальный aiohttp-прокси:

```
Браузер → Nginx (Docker, :3000) → aiohttp proxy (:8043) → Native Orthanc (:8042)
```

- **Nginx**: раздаёт фронтенд, проксирует API и DICOM-запросы
- **aiohttp proxy**: асинхронный прокси для DICOM Web (query, retrieve, viewer URL)
- **Native Orthanc**: DICOM-сервер (port 8042, только localhost)

Stone Web Viewer подключается через iframe с `app.json`, который генерируется Nginx.

## Структура проекта

```
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI routers
│   │   ├── models/        # SQLAlchemy models
│   │   ├── schemas/       # Pydantic schemas
│   │   ├── services/      # Business logic
│   │   ├── templates/     # Jinja2 (PDF)
│   │   └── main.py        # FastAPI app
│   ├── alembic/           # Migrations
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/           # Axios client
│   │   ├── components/    # React components
│   │   ├── hooks/         # Custom hooks
│   │   ├── pages/         # Page components
│   │   ├── stores/        # Zustand stores
│   │   └── i18n/          # Translations
│   └── nginx.conf         # Nginx config
├── docker-compose.yml
├── orthanc-proxy.py       # DICOM proxy (aiohttp)
├── start-proxy.vbs        # Proxy launcher (hidden window)
├── start-server.bat       # Auto-detect IP + full launch
├── detect_ip.py           # LAN IP detection
└── .env                   # Generated environment variables
```

## Лицензия

MIT License — для образовательных и демонстрационных целей.
