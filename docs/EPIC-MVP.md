# EPIC: RIS MVP — Полная реализация

**Статус:** Готово к разработке · **Команда:** AI-assisted · **2026-06-13**

> Источники истины: [ТЗ v3](../tz/ris-mvp-tz-v3.md) · [Wireframes](../tz/wireframes.html) · [BPMN](../tz/ris-mvp-bpmn.md) · [Шаблоны](REPORT-TEMPLATES.md)

---

## Принципы разработки

1. **UI first** — каждый модуль начинается с реализации экрана из wireframes. Wireframes — источник истины для верстки.
2. **Типизация везде** — TypeScript strict mode на фронте, Pydantic v2 на беке.
3. **Тест = AC** — каждый acceptance criteria = один тест. Нет теста — задача не закрыта.
4. **Русский везде в UI** — все лейблы, статусы, сообщения об ошибках на русском.
5. **Миграции сразу** — каждое изменение схемы = Alembic-миграция в том же PR.
6. **Orthanc через адаптер** — никогда не вызывать Orthanc REST напрямую из бизнес-логики. Только через `OrthancAdapter`.

---

## Структура проекта (src/)

```
src/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/             # роуты по модулям
│   │   │   ├── patients.py
│   │   │   ├── orders.py
│   │   │   ├── schedule.py
│   │   │   ├── worklist.py
│   │   │   ├── reports.py
│   │   │   ├── refs.py
│   │   │   ├── users.py
│   │   │   └── stats.py
│   │   ├── models/          # SQLAlchemy ORM
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── services/        # бизнес-логика
│   │   ├── adapters/
│   │   │   └── orthanc.py   # OrthancAdapter
│   │   ├── auth/            # JWT + RBAC
│   │   └── core/            # config, db, deps
│   ├── alembic/             # миграции
│   ├── scripts/
│   │   └── seed_refs.py     # загрузка МКБ-10 + тарификатора
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── pages/           # по экранам wireframes
│   │   ├── components/      # переиспользуемые компоненты
│   │   ├── hooks/
│   │   ├── api/             # API клиент (axios/tanstack-query)
│   │   ├── stores/          # Zustand
│   │   ├── i18n/            # ru.json, kz.json
│   │   └── theme/           # CSS переменные light/dark
│   └── tests/
├── orthanc/
│   ├── orthanc.json         # конфигурация
│   └── plugins/
│       └── notify_ris.py    # webhook OnStoredInstance
└── docker-compose.yml
```

---

## Модель данных (PostgreSQL)

```sql
-- Справочники
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name_ru VARCHAR(200) NOT NULL,
    name_kz VARCHAR(200),
    license_number VARCHAR(50),
    address TEXT,
    phone VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE services (  -- тарификатор МЗ РК
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code_gombp VARCHAR(20) NOT NULL,
    code_osms VARCHAR(20),
    name_ru VARCHAR(300) NOT NULL,
    name_kz VARCHAR(300),
    modality VARCHAR(10) NOT NULL,
    body_part VARCHAR(100),
    tariff_gombp NUMERIC(10,2),
    tariff_osms NUMERIC(10,2),
    tariff_paid NUMERIC(10,2),
    duration_min INTEGER NOT NULL DEFAULT 20,
    contrast_agent BOOLEAN DEFAULT FALSE,
    valid_from DATE NOT NULL,
    valid_to DATE,
    version INTEGER NOT NULL DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE diagnosis_icd (  -- МКБ-10
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(10) UNIQUE NOT NULL,
    name_ru VARCHAR(300) NOT NULL,
    name_kz VARCHAR(300),
    chapter VARCHAR(5),
    is_leaf BOOLEAN DEFAULT TRUE
);

CREATE TABLE devices (  -- аппараты
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    name VARCHAR(200) NOT NULL,
    modality_type VARCHAR(10) NOT NULL,
    ae_title VARCHAR(16) UNIQUE NOT NULL,
    ip_address VARCHAR(15),
    dicom_port INTEGER DEFAULT 104,
    schedule_start TIME DEFAULT '08:00',
    schedule_end TIME DEFAULT '18:00',
    working_days INTEGER[] DEFAULT '{1,2,3,4,5}',  -- 1=Пн...7=Вс
    status VARCHAR(20) DEFAULT 'ACTIVE',  -- ACTIVE|MAINTENANCE|BROKEN|RETIRED
    notes TEXT
);

CREATE TABLE protocol_templates (  -- шаблоны протоколов
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    name_ru VARCHAR(200) NOT NULL,
    name_kz VARCHAR(200),
    modality VARCHAR(10) NOT NULL,
    body_part VARCHAR(100),
    service_id UUID REFERENCES services(id),
    fields_schema JSONB NOT NULL DEFAULT '[]',
    description_template TEXT,
    conclusion_template TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Пользователи
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    login VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(200) NOT NULL,
    role VARCHAR(30) NOT NULL,  -- REGISTRAR|TECHNOLOGIST|RADIOLOGIST|HEAD|REFERRER|ADMIN
    last_name VARCHAR(100) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    middle_name VARCHAR(100),
    specialization VARCHAR(200),
    license_number VARCHAR(50),
    email VARCHAR(200),
    phone VARCHAR(20),
    default_device_id UUID REFERENCES devices(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Пациенты
CREATE TABLE patients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    iin VARCHAR(12) UNIQUE NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    middle_name VARCHAR(100),
    birth_date DATE NOT NULL,
    gender VARCHAR(1) NOT NULL,  -- M|F
    phone VARCHAR(20),
    email VARCHAR(200),
    benefit_category VARCHAR(20) DEFAULT 'NONE',  -- GOMBP|OSMS|DISABLED|NONE
    document_type VARCHAR(20),
    document_number VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES users(id)
);

-- Направления
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    accession_number VARCHAR(16) UNIQUE NOT NULL,
    patient_id UUID NOT NULL REFERENCES patients(id),
    service_id UUID NOT NULL REFERENCES services(id),
    modality VARCHAR(10) NOT NULL,
    body_part VARCHAR(100),
    priority VARCHAR(10) NOT NULL DEFAULT 'ROUTINE',  -- ROUTINE|URGENT|CITO
    financing_type VARCHAR(10) NOT NULL DEFAULT 'PAID',  -- GOMBP|OSMS|PAID
    referring_physician_id UUID REFERENCES users(id),
    referring_physician_name VARCHAR(200),  -- для внешних направителей
    diagnosis_icd_id UUID REFERENCES diagnosis_icd(id),
    clinical_notes TEXT,
    contrast_agent BOOLEAN DEFAULT FALSE,
    status VARCHAR(20) NOT NULL DEFAULT 'NEW',
    cancelled_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES users(id)
);

CREATE TABLE appointments (  -- запись в расписание
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID UNIQUE NOT NULL REFERENCES orders(id),
    device_id UUID NOT NULL REFERENCES devices(id),
    technologist_id UUID REFERENCES users(id),
    slot_start TIMESTAMPTZ NOT NULL,
    slot_end TIMESTAMPTZ NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE studies (  -- проведённое исследование
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID UNIQUE NOT NULL REFERENCES orders(id),
    study_instance_uid VARCHAR(64) UNIQUE,
    orthanc_study_id VARCHAR(64),
    technologist_id UUID REFERENCES users(id),
    acquired_at TIMESTAMPTZ,
    qc_status VARCHAR(10),  -- ACCEPTED|RETAKE
    qc_attempts JSONB DEFAULT '[]',  -- [{attempt, status, comment, ts}]
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE reports (  -- заключения
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id),
    radiologist_id UUID REFERENCES users(id),
    protocol_template_id UUID REFERENCES protocol_templates(id),
    structured_fields JSONB DEFAULT '{}',
    description_text TEXT,
    conclusion_text TEXT,
    critical_finding BOOLEAN DEFAULT FALSE,
    diagnosis_icd_codes VARCHAR(10)[] DEFAULT '{}',
    status VARCHAR(10) NOT NULL DEFAULT 'DRAFT',  -- DRAFT|SIGNED|ISSUED
    version INTEGER NOT NULL DEFAULT 1,
    parent_report_id UUID REFERENCES reports(id),
    second_opinion_of_report_id UUID REFERENCES reports(id),
    signed_at TIMESTAMPTZ,
    content_hash VARCHAR(64),  -- SHA-256 при подписи
    issued_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Аудит
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID,
    action VARCHAR(20) NOT NULL,  -- CREATE|UPDATE|VIEW|SIGN|ISSUE|CANCEL
    user_id UUID REFERENCES users(id),
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    before_json JSONB,
    after_json JSONB,
    ip_address VARCHAR(45),
    session_id VARCHAR(100)
);

-- Индексы производительности
CREATE INDEX idx_orders_patient ON orders(patient_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_an ON orders(accession_number);
CREATE INDEX idx_reports_order ON reports(order_id);
CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_user ON audit_log(user_id, timestamp);
CREATE INDEX idx_patients_iin ON patients(iin);
CREATE INDEX idx_appointments_device_slot ON appointments(device_id, slot_start);
```

---

## Спринт 1 — Основа (Неделя 1–2)

### ЗАДАЧА 1.1: Docker Compose окружение

**Файл:** `docker-compose.yml`

```yaml
services:
  api:
    build: ./backend
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgresql+asyncpg://ris:ris@db:5432/ris
      ORTHANC_URL: http://orthanc:8042
      SECRET_KEY: ${SECRET_KEY}
      ENVIRONMENT: development
    depends_on: [db, orthanc]
    volumes: ["./backend:/app"]

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ris
      POSTGRES_USER: ris
      POSTGRES_PASSWORD: ris
    volumes: ["pgdata:/var/lib/postgresql/data"]
    ports: ["5432:5432"]

  orthanc:
    image: orthancteam/orthanc:latest
    ports: ["8042:8042", "4242:4242"]
    volumes:
      - orthancdata:/var/lib/orthanc/db
      - ./orthanc/orthanc.json:/etc/orthanc/orthanc.json:ro
      - ./orthanc/plugins:/scripts
    environment:
      ORTHANC__REGISTERED_USERS: '{"orthanc": "orthanc"}'

volumes:
  pgdata:
  orthancdata:
```

**Orthanc конфиг** (`orthanc/orthanc.json`): включить MWL, DICOMweb, разрешить RIS IP.

**Acceptance criteria:**
1. `docker compose up -d` — все 3 сервиса HEALTHY
2. `GET http://localhost:8042/system` возвращает JSON Orthanc
3. `GET http://localhost:8000/health` возвращает `{"status":"ok"}`

---

### ЗАДАЧА 1.2: Схема БД + Alembic

Создать все таблицы из раздела «Модель данных» выше как SQLAlchemy 2.0 models + Alembic initial migration.

**Acceptance criteria:**
1. `alembic upgrade head` выполняется без ошибок на чистой БД
2. `alembic downgrade base` откатывается без ошибок
3. Все индексы созданы

---

### ЗАДАЧА 1.3: Аутентификация JWT + RBAC

**Эндпоинты:**
- `POST /api/auth/login` → `{access_token, token_type, user}`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `GET /api/auth/me`

**RBAC middleware:** декоратор `@require_roles(["REGISTRAR", "ADMIN"])` для каждого роута.

**Acceptance criteria:**
1. Login с верными кредами → JWT токен
2. Роль REFERRER не может GET `/api/patients/` (не своих) → 403
3. Пароль хранится как argon2 hash — `SELECT password_hash FROM users WHERE login='test'` возвращает строку начинающуюся с `$argon2`
4. Истёкший токен → 401

---

### ЗАДАЧА 1.4: React + Ant Design + темная/светлая тема

Scaffold фронтенда:
- Vite + React 19 + TypeScript strict
- Ant Design 5.x с кастомизированными токенами из `docs/tz/ui-decisions.md`
- Роутинг: React Router v6
- Глобальный state: Zustand
- API клиент: TanStack Query + axios
- i18n: react-i18next (ru.json — первый язык)

**Тёмная/светлая тема:**
- CSS custom properties из `wireframes.html` (`--c-bg`, `--c-surface`, etc.)
- Ant Design ConfigProvider с динамической темой
- Переключатель в Header, сохранение в `localStorage`
- Анимация 0.35s (как в wireframes)

**Acceptance criteria:**
1. `npm run dev` открывает страницу логина
2. Переключение темы работает на всех страницах
3. `npm run typecheck` — 0 ошибок
4. `npm run lint` — 0 ошибок

---

### ЗАДАЧА 1.5: Загрузка справочников

Скрипт `backend/scripts/seed_refs.py`:
- Импорт МКБ-10 из `docs/refs/icd10-radiology.json`
- Импорт тарификатора из `docs/refs/tariff-radiology.csv`
- Создание организации по умолчанию
- Создание пользователя admin (пароль из ENV)

**Acceptance criteria:**
1. `python scripts/seed_refs.py` выполняется без ошибок
2. `SELECT COUNT(*) FROM diagnosis_icd` > 90
3. `SELECT COUNT(*) FROM services` > 35
4. Повторный запуск — idempotent (нет дублей)

---

## Спринт 2 — Регистратура (Неделя 2–3)

### ЗАДАЧА 2.1: Пациенты — API

**Эндпоинты:**
```
GET    /api/patients/?search=&page=&limit=
GET    /api/patients/{id}
POST   /api/patients/
PUT    /api/patients/{id}
GET    /api/patients/{id}/history  (список направлений)
```

**Валидация ИИН** (см. `docs/refs/validation.md`):
- 12 цифр
- Дата рождения из цифр 1-6 должна быть реальной
- Контрольная цифра по алгоритму W1/W2
- Уникальность в рамках организации

**Acceptance criteria:**
1. `POST /patients` с невалидным ИИН → 422 с сообщением "ИИН не прошёл контроль цифры"
2. `POST /patients` с дублем ИИН → 409 с `{existing_patient_id}`
3. `GET /patients?search=байж` находит по ФИО и ИИН
4. Аудит-запись создаётся при каждом CREATE/UPDATE

---

### ЗАДАЧА 2.2: Пациенты — UI

Реализовать экраны из wireframes:
- **Список пациентов** (`/patients`) — поиск, таблица, пагинация
- **Карточка пациента** (`/patients/:id`) — реквизиты + история исследований

**UI требования (из wireframes.html → экран «Пациенты» и «Карточка пациента»):**
- Поиск live (debounce 300ms) при вводе ≥ 3 символов
- При дубле ИИН — жёлтое предупреждение с ссылкой
- История исследований — табы по модальностям
- Кнопка "+ Направление" открывает форму создания заказа

**Acceptance criteria:**
1. Поиск "байж" за < 500ms выдаёт результаты
2. Карточка пациента отображает все поля из wireframes
3. История фильтруется по модальности без перезагрузки

---

### ЗАДАЧА 2.3: Направления — API

```
POST   /api/orders/
GET    /api/orders/{id}
PUT    /api/orders/{id}/status   {status, reason?}
DELETE /api/orders/{id}          (→ CANCELLED)
GET    /api/orders/{id}/pdf      (PDF направления)
```

**Генерация Accession Number:**
```python
def generate_accession_number() -> str:
    date_part = datetime.now().strftime("%y%m%d")
    seq = get_next_sequence("accession_number")  # атомарный счётчик
    return f"{date_part}-{seq:05d}"
```

**Acceptance criteria:**
1. AN уникален — нагрузочный тест 100 параллельных создания без коллизий
2. PDF содержит: org logo placeholder, ИИН пациента, код услуги, МКБ-10, AN, дату
3. Переход в недопустимый статус → 422

---

### ЗАДАЧА 2.4: Расписание — API + UI

**API:**
```
GET  /api/schedule/slots?device_id=&date=&modality=
POST /api/schedule/appointments/          (создать запись)
PUT  /api/schedule/appointments/{id}      (перенести)
DEL  /api/schedule/appointments/{id}      (отменить)
```

**UI — Calendar:** (wireframes: экран «Расписание»)
- Недельный вид: 7 колонок × временные слоты
- Слот = `duration_min` из services
- Цвет слота по статусу (свободно / запланировано / в процессе)
- Drag-and-drop для переноса
- Подсветка выбранного слота при создании записи

**Acceptance criteria:**
1. Двойная запись на один слот → 409
2. Слот вне рабочего времени аппарата недоступен
3. Запись создаётся и тут же видна в календаре (WS или optimistic update)

---

## Спринт 3 — DICOM + Worklist (Неделя 3–4)

### ЗАДАЧА 3.1: OrthancAdapter

`backend/app/adapters/orthanc.py`:

```python
class OrthancAdapter:
    async def publish_mwl(self, order: Order) -> None:
        """Создать MWL запись в Orthanc при переходе в SCHEDULED"""

    async def get_study(self, study_instance_uid: str) -> dict:
        """GET /studies/{uid} из Orthanc"""

    async def get_viewer_url(self, study_instance_uid: str) -> str:
        """Ссылка на Stone Web Viewer"""

    async def list_new_studies(self, since: datetime) -> list[dict]:
        """Для поллинга — список студий новее since"""
```

**MWL DICOM теги** (см. `docs/tz/ris-mvp-bpmn.md` раздел 8.1):
- (0008,0050) AccessionNumber
- (0010,0010) PatientName
- (0010,0020) PatientID → ИИН
- (0010,0030) PatientBirthDate
- (0010,0040) PatientSex
- (0020,000D) StudyInstanceUID
- (0008,0060) Modality
- (0040,0001) ScheduledStationAETitle
- (0040,0002) ScheduledProcedureStepDate
- (0040,0003) ScheduledProcedureStepTime

**Acceptance criteria:**
1. При SCHEDULED → Orthanc MWL GET `/modalities/*/worklist` видит запись
2. OrthancAdapter тестируется с мок-HTTP (httpx MockTransport) — нет зависимости от реального Orthanc в unit-тестах

---

### ЗАДАЧА 3.2: Webhook OnStoredInstance

`orthanc/plugins/notify_ris.py`:
```python
def OnStoredInstance(dicom, instanceId):
    study_uid = dicom.get("0020,000D")
    accession = dicom.get("0008,0050")
    requests.post("http://api:8000/api/webhook/orthanc/stored", json={
        "study_instance_uid": study_uid,
        "accession_number": accession,
        "orthanc_study_id": instanceId
    })
```

**RIS endpoint** `POST /api/webhook/orthanc/stored`:
- Найти Order по AN / Study UID
- Если найден → `order.status = ACQUIRED`
- Если не найден → запись в таблицу `unmatched_studies`
- Уведомление через WebSocket всем лаборантам данного аппарата

**Acceptance criteria:**
1. C-STORE в Orthanc → через < 5 с статус Order меняется на СНИМКИ ПОЛУЧЕНЫ
2. Несопоставленная студия → появляется в экране «Несопоставлено»
3. Лаборант видит уведомление без перезагрузки страницы

---

### ЗАДАЧА 3.3: Worklist UI

Экран «Worklist» (wireframes):
- Фильтры: дата, статус, приоритет
- Таблица с кнопками действий: [Прибыл] [Принять QC] [Переснять]
- Строки CITO — красный фон
- Автообновление через WebSocket
- Форма QC при нажатии «Переснять»

**Acceptance criteria:**
1. Нажать [Прибыл] → статус меняется без перезагрузки
2. Форма QC появляется инлайн (не модал)
3. WebSocket реконнект при разрыве — автоматический

---

## Спринт 4 — Описание и заключение (Неделя 4–5)

### ЗАДАЧА 4.1: Шаблоны протоколов — API + UI

**API:**
```
GET  /api/protocol-templates/?modality=&service_id=
GET  /api/protocol-templates/{id}
POST /api/protocol-templates/
PUT  /api/protocol-templates/{id}
```

**Поле `fields_schema` (JSONB):**
```json
[
  {
    "field_key": "white_matter",
    "label_ru": "Белое вещество",
    "type": "select",
    "options": ["Норма", "Очаги демиелинизации", "Диффузные изменения", "Лейкоэнцефалопатия"],
    "required": false
  },
  {
    "field_key": "lesion_size_mm",
    "label_ru": "Размер очагов (мм)",
    "type": "number",
    "unit": "мм",
    "required": false
  }
]
```

**Автовыбор шаблона:** при открытии описания → `GET /protocol-templates/?service_id={order.service_id}` → первый результат загружается автоматически.

**UI — конструктор шаблонов** (wireframes: экран «Шаблоны»):
- Список шаблонов с фильтром по модальности
- Форма редактирования с drag-and-drop полей
- Предпросмотр шаблона

**Acceptance criteria:**
1. Администратор создаёт шаблон с 5 полями → шаблон применяется при описании
2. Версии шаблонов: изменение создаёт `version+1`, старая версия остаётся
3. Шаблон загружается автоматически по `service_id`

**Сид базовых шаблонов:** при первом запуске `seed_refs.py` загружать шаблоны из `docs/team/REPORT-TEMPLATES.md`.

---

### ЗАДАЧА 4.2: Экран описания — 3-колоночный layout ⭐ КЛЮЧЕВОЙ ЭКРАН

Самый важный экран системы. Источник истины — wireframes экран «Описание».

**Три колонки:**

**Левая (260px):** данные исследования
- Все поля из направления (пациент, ИИН, услуга, клин. сведения, направитель, предв. диагноз)
- Тайм-лайн статусов с timestamp каждого перехода
- Тип финансирования (ГОБМП/ОСМС/Платно)

**Центральная (flex):** вьюер + форма описания
- Stone Web Viewer Orthanc в `<iframe src="{viewer_url}?study={study_uid}">` (высота ~280px)
- Выбор шаблона протокола (autocomplete)
- Динамическая форма из `fields_schema` (radio/select/text/number поля)
- Textarea «Описание» (до 10 000 символов)
- Textarea «Заключение» (обязательное)

**Правая (310px):** диагноз + подпись
- Autocomplete МКБ-10 (поиск по коду и названию)
- Мультиселект диагнозов (основной + сопутствующие)
- Чекбокс «Критическая находка»
- Блок подписи (ФИО, должность, timestamp, SHA-256)
- Кнопки: [Сохранить черновик] [Подписать] [Выдать PDF]

**Keyboard shortcuts:**
- `Ctrl+S` — сохранить черновик
- `Ctrl+Enter` — подписать
- `Ctrl+Shift+I` — фокус на поле «Описание»

**Acceptance criteria:**
1. Вьюер открывается в том же экране без перехода на новую вкладку
2. Форма динамически меняется при смене шаблона (без перезагрузки)
3. После подписи — все поля заблокированы, правка невозможна
4. SHA-256 хэш заключения сохранён в `reports.content_hash`

---

### ЗАДАЧА 4.3: Подпись (ЭЦП-ready) + PDF

**Подпись:**
```python
class SignatureProvider:
    async def sign(self, report_id: UUID, user_id: UUID) -> SignatureResult:
        """MVP: SHA-256(conclusion_text + signed_at + user_id)"""

    async def verify(self, report_id: UUID) -> bool:
        """Проверка хэша"""
```

Интерфейс изолирован → позже подключается NCALayer без изменения логики.

**PDF генерация** (WeasyPrint):
- Шаблон HTML → PDF
- Обязательные реквизиты (НПА РК): организация, лицензия МЗ РК, ИИН пациента, AN, дата, врач, код МКБ
- Водяной знак «ЧЕРНОВИК» для неподписанных
- При `critical_finding=True` — красный штамп «КРИТИЧЕСКАЯ НАХОДКА»

**Acceptance criteria:**
1. PDF скачивается за < 3 с
2. PDF содержит все обязательные реквизиты НПА РК
3. Попытка PUT подписанного отчёта → 403 "Подписанный документ неизменяем"

---

### ЗАДАЧА 4.4: cito-уведомления + второе мнение

**cito:** при `ISSUED` с `critical_finding=True`:
- WebSocket уведомление всем врачам-направителям пациента
- Badge с числом непрочитанных уведомлений в сайдбаре
- Запись в `audit_log` action=`CITO_NOTIFICATION`

**Второе мнение:**
- `POST /api/reports/{id}/second-opinion` → создаёт новый Report c `second_opinion_of_report_id`
- Оригинальный Report не изменяется
- Рецензент получает уведомление

**Acceptance criteria:**
1. ISSUED с critical_finding → направитель видит уведомление без перезагрузки
2. Второй отчёт связан с оригиналом, оба видны в карточке пациента

---

## Спринт 5 — Справочники + Статистика (Неделя 5–6)

### ЗАДАЧА 5.1: Управление справочниками (Admin UI)

Реализовать экраны из wireframes:
- **Тарификатор** — таблица + форма редактирования + импорт CSV
- **МКБ-10** — поиск (только чтение)
- **Аппараты** — полный CRUD + проверка DICOM-соединения
- **Пользователи** — полный CRUD + сброс пароля
- **Шаблоны протоколов** — список + конструктор (Задача 4.1)

**Acceptance criteria для каждого справочника:**
1. Создание записи отражается без перезагрузки
2. Деструктивные действия (удаление) требуют подтверждения
3. Импорт CSV показывает прогресс и сводку ошибок

---

### ЗАДАЧА 5.2: Дашборд и статистика

**Экраны:** wireframes «Дашборд» + «Статистика».

**API:**
```
GET /api/stats/dashboard?period=today|week|month
GET /api/stats/turnaround?from=&to=&device_id=&radiologist_id=
GET /api/stats/load?from=&to=
GET /api/stats/export?format=csv|xlsx&from=&to=
```

**Метрики:**
- Turnaround time = `issued_at - created_at` (в минутах)
- Время ожидания описания = `signed_at - acquired_at`
- Нагрузка = число исследований по аппарату / врачу
- Разбивка по типу финансирования (ГОБМП/ОСМС/Платно)
- Доля просроченных (TAT > настраиваемый порог)

**Acceptance criteria:**
1. Дашборд загружается < 2 с при 1000 записей
2. CSV-экспорт корректно экспортирует UTF-8 (открывается в Excel)
3. TAT вычисляется точно — тест: создать order, проставить все статусы, проверить TAT

---

## Спринт 6 — Аудит + Полировка (Неделя 6)

### ЗАДАЧА 6.1: Аудит-лог

- `audit_log` заполняется автоматически через SQLAlchemy events
- API: `GET /api/audit?entity_type=&entity_id=&from=&to=`
- UI: таблица в разделе Администратор
- Журнал входов пользователя: `GET /api/users/{id}/login-history`

**Acceptance criteria:**
1. Каждое CREATE/UPDATE/SIGN/ISSUE порождает запись в audit_log
2. Записи audit_log не удаляются через API (нет DELETE эндпоинта)
3. `before_json` и `after_json` содержат корректные данные при UPDATE

---

### ЗАДАЧА 6.2: UI/UX финальная полировка ⭐

**Приоритеты из wireframes и ui-decisions.md:**

1. **Статусы везде на русском** — проверить все badge компоненты
2. **CITO строки** — красный фон `tr.cito-row` в worklist и дашборде
3. **Пустые состояния** — заглушки для пустых списков (нет пациентов, нет исследований)
4. **Загрузка** — skeleton-загрузчики для таблиц и карточек
5. **Ошибки API** — тосты с понятным текстом на русском
6. **Адаптивность** — планшет 768px минимум
7. **Keyboard navigation** — Tab-order в формах
8. **Focus states** — видимые outline при навигации с клавиатуры

**Acceptance criteria:**
1. Lighthouse accessibility score ≥ 85
2. Нет console.error в production build
3. Переключение темы анимировано (0.35 сек, как в wireframes)
4. Все формы валидируют поля с русскими сообщениями об ошибках

---

### ЗАДАЧА 6.3: Нагрузочное тестирование

```bash
# k6 тест
k6 run --vus 50 --duration 60s load-test.js
```

**Целевые метрики:**
- Открытие worklist < 2 с при 50 VU
- API p95 < 500 мс
- 0 ошибок при параллельном создании 100 заказов

---

## Acceptance Criteria для всего MVP

MVP считается готовым, когда выполнен следующий сценарий без ошибок:

```
1. Регистратор входит → создаёт пациента (ИИН валидируется)
2. Регистратор создаёт направление МРТ головного мозга (ОСМС)
3. Регистратор записывает в расписание → AN создаётся
4. Orthanc получает C-STORE → через 5 сек Order = СНИМКИ ПОЛУЧЕНЫ
5. Лаборант принимает QC → Order = К ОПИСАНИЮ
6. Врач открывает экран описания → видит снимки в вьюере Orthanc
7. Врач выбирает шаблон МРТ головного мозга → заполняет структурированные поля
8. Врач указывает МКБ-10: G35 → подписывает → Order = ПОДПИСАНО
9. Врач выдаёт → Order = ВЫДАНО → PDF скачивается
10. Дашборд показывает TAT этого исследования
11. Аудит-лог содержит все 10 шагов выше
```

---

## Открытые вопросы (ответить до начала Спринта 1)

1. **Хостинг:** VPS в Казтелеком / KDDI / Jusan Cloud — где именно?
2. **GitHub репо:** создать организацию и репо, настроить CI
3. **Orthanc MWL плагин:** доступен в Docker-образе `orthancteam/orthanc`? Проверить.
4. **Актуальный тарификатор МЗ РК:** скачать свежий Excel (2024–2025) и добавить в `docs/refs/`
5. **Stone Web Viewer:** убедиться, что работает без CORS проблем при embed через iframe
