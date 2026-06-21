# Архитектурное описание RIS MVP

## 1. Общая архитектура

### Многоуровневая архитектура (Layered Architecture)

```
┌─────────────────────────────────────────────────────────────┐
│  Presentation Layer (Frontend)                               │
│  React 19 + TypeScript + Ant Design                         │
│  - Pages (Dashboard, Patients, Orders, ...)                 │
│  - Components (Layout, Forms, Tables)                       │
│  - State (Zustand stores)                                   │
│  - Theme (Light/Dark provider)                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ HTTP/REST + JWT
┌─────────────────────────────────────────────────────────────┐
│  Application Layer (Backend API)                             │
│  FastAPI Routers                                            │
│  - Auth, Patients, Orders, Reports, Refs                   │
│  - Schedule, Worklist, Stats, Admin                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Business Logic Layer (Services)                             │
│  - Status Machine (Order state transitions)                 │
│  - Accession Number (atomic generation)                     │
│  - PDF Generator (WeasyPrint + Jinja2)                      │
│  - Audit Logger (SQLAlchemy event listeners)                │
│  - Auth (JWT + RBAC, 6 roles)                               │
│  - Password hashing (Argon2)                                │
│  - Report signing (SHA-256 content_hash)                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Data Access Layer (ORM)                                     │
│  SQLAlchemy 2.0 (async)                                     │
│  - Models (13 entities + UnmatchedStudy)                    │
│  - Relationships (Foreign Keys)                             │
│  - Migrations (Alembic)                                     │
│  - 8 performance indexes                                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Data Layer                                                  │
│  PostgreSQL 16  │  Orthanc (DICOM)                          │
└─────────────────────────────────────────────────────────────┘
```

## 2. Модель данных (ER-диаграмма)

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Organization │────<│    User      │     │   Patient    │
│──────────────│     │──────────────│     │──────────────│
│ id (PK)      │     │ id (PK)      │     │ id (PK)      │
│ name_ru      │     │ login (UQ)   │     │ iin (UQ, 12) │
│ license      │     │ password_hash│     │ last_name    │
│ ...          │     │ role (enum)  │     │ first_name   │
└──────────────┘     │ ...          │     │ birth_date   │
                     └──────┬───────┘     │ gender (M/F) │
                            │              │ benefit_cat  │
                            │              └──────┬───────┘
                            │                     │
                     ┌──────┴───────┐     ┌─────┴────────┐
                     │   Device     │     │    Order     │
                     │──────────────│     │──────────────│
                     │ id (PK)      │     │ id (PK)      │
                     │ name         │     │ accession_no │
                     │ modality_type│     │ patient_id   │───────┐
                     │ ae_title     │     │ service_id   │───────┼───────┐
                     │ status       │     │ modality     │       │       │
                     └──────────────┘     │ status       │       │       │
                                          │ priority     │       │       │
                                          │ financing    │       │       │
                                          └──────┬───────┘       │       │
                                                 │               │       │
                     ┌───────────────────────────┼───┐           │       │
                     │                           │   │           │       │
              ┌──────┴───────┐           ┌───────┴───┴───┐ ┌────┴───┐ ┌─┴──────────┐
              │ Appointment  │           │     Study     │ │Service │ │DiagnosisICD│
              │──────────────│           │───────────────│ │────────│ │────────────│
              │ id (PK)      │           │ id (PK)       │ │id (PK) │ │id (PK)     │
              │ order_id(FK) │           │ order_id(FK,UQ)│ │code_g  │ │code (UQ)   │
              │ device_id(FK)│           │ study_uid(UQ) │ │name_ru │ │name_ru     │
              │ slot_start   │           │ orthanc_id    │ │modality│ │chapter     │
              │ slot_end     │           │ qc_status     │ │tariffs │ │is_leaf     │
              └──────────────┘           └───────────────┘ └────────┘ └────────────┘
                                                  │
                                          ┌───────┴───────┐
                                          │    Report     │
                                          │───────────────│
                                          │ id (PK)       │
                                          │ order_id (FK) │
                                          │ radiologist_id│
                                          │ conclusion    │
                                          │ status (enum) │
                                          │ content_hash  │ ← ЭЦP-ready
                                          │ signed_at     │
                                          │ issued_at     │
                                          └───────────────┘
```

## 3. Потоки данных

### 3.1. Создание направления

```
Регистратор ──► POST /api/orders ──► OrderCreate schema
                                      │
                                      ▼
                              ┌──────────────┐
                              │ Generate AN  │ (YYMMDD-NNNNN)
                              │ Validate pt  │
                              │ Create Order │
                              │ status = NEW │
                              └──────┬───────┘
                                     │
                                     ▼
                              PostgreSQL (orders)
                                     │
                                     ▼
                              Response: OrderResponse
```

### 3.2. Жизненный цикл направления

```
NEW ──► SCHEDULED ──► ARRIVED ──► IN_PROGRESS ──► ACQUIRED ──► TO_REPORT
 │         │             │              │              │             │
 │         │             │              │              │             ▼
 │         │             │              │              │        REPORTING
 │         │             │              │              │             │
 │         │             │              │              │             ▼
 │         │             │              │              │           SIGNED
 │         │             │              │              │             │
 │         │             │              │              │             ▼
 │         │             │              │              │           ISSUED
 │         │             │              │              │
 │         │             │              │              └── QC: ACCEPTED/RETAKE
 │         │             │              │
 │         │             │              └── DICOM images from modality
 │         │             │
 │         │             └── Patient arrived at reception
 │         │
 │         └── Appointment created in schedule
 │
 └── Order created by registrar
```

### 3.3. Подписание заключения (ЭЦП-ready)

```
Радиолог ──► PUT /api/reports/{id} ──► Edit description/conclusion
                                          │
                                          ▼
                                    POST /api/reports/{id}/sign
                                          │
                                          ▼
                                    ┌─────────────────┐
                                    │ 1. Concatenate  │
                                    │  conclusion +   │
                                    │  timestamp +    │
                                    │  user_id        │
                                    │ 2. SHA-256 hash │
                                    │ 3. Save hash    │
                                    │ 4. status=SIGNED│
                                    └─────────────────┘
                                          │
                                          ▼
                                    PostgreSQL (reports)
                                          │
                                          ▼
                                    Future: NCA eGov Mobile
```

## 4. Безопасность

### 4.1. Аутентификация
- JWT токены с временем жизни 8 часов
- Argon2 хеширование паролей
- Хранение в localStorage с защитой XSS

### 4.2. Авторизация (RBAC)

| Роль | Права |
|------|-------|
| REGISTRAR | patients, orders, schedule |
| TECHNOLOGIST | worklist, QC |
| RADIOLOGIST | reports (create, edit, sign, issue) |
| HEAD | stats, second opinion, admin (read) |
| REFERRER | свои пациенты и заказы только |
| ADMIN | full access |

### 4.3. Валидация данных
- Pydantic schemas для всех входных данных
- ИИН валидация (12 цифр + проверка даты)
- SQL-инъекции защита через ORM
- XSS защита через React escaped rendering

## 5. Интеграции

### 5.1. DICOM (Orthanc)
- OrthancAdapter — абстракция для взаимодействия с Orthanc
- REST API для получения DICOM-данных
- MWL (Modality Worklist) публикация при переходе заказа в SCHEDULED
- OnStoredInstance webhook → POST /api/webhook/orthanc/stored
- C-STORE для приема снимков
- UnmatchedStudy — несопоставленные исследования
- Stone Web Viewer для встраивания в iframe

### 5.2. СЭМД (Future)
- HL7 FHIR API endpoint (заглушка)
- Соответствие приказу МЗ РК от 10.02.2023 № 47

### 5.3. NCA eGov Mobile (Future)
- SOAP-сервис для ЭЦП
- SHA-256 хеши подготовлены для подписания

## 6. Масштабирование

### 6.1. Горизонтальное
- Stateless backend — возможность запуска multiple instances
- PostgreSQL read replicas для отчетов
- При масштабировании: добавить Redis для WS pub/sub

### 6.2. Вертикальное
- Индексы на часто запрашиваемые поля
- Materialized views для статистики
- Кэширование справочников

## 7. Мониторинг

### 7.1. Health Checks
- `/health` — общий статус
- Orthanc: `GET /system` — статус DICOM-сервера

### 7.2. Метрики (Future)
- Prometheus /metrics endpoint
- Grafana dashboards

## 8. Резервное копирование

### 8.1. PostgreSQL
```bash
# Ежедневный дамп
pg_dump -h localhost -U ris -d ris > ris-backup-$(date +%Y%m%d).sql
```

### 8.2. DICOM
- Orthanc автоматически сохраняет в `/var/lib/orthanc/db`
- Volume backup через Docker
