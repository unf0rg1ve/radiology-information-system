# API Документация RIS MVP

## Базовый URL
```
http://localhost:8000/api
```

## Аутентификация
Все endpoints (кроме /auth/login) требуют JWT токен в заголовке:
```
Authorization: Bearer <token>
```

## Content-Type
```
Content-Type: application/json
```

---

## Authentication

### POST /auth/login
Вход в систему

**Request:**
```json
{
  "login": "admin",
  "password": "admin123"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 480,
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "login": "admin",
    "role": "ADMIN",
    "first_name": "Системы",
    "last_name": "Администратор",
    "full_name": "Администратор Системы"
  }
}
```

### GET /auth/me
Текущий пользователь

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "login": "admin",
  "role": "ADMIN",
  "first_name": "Системы",
  "last_name": "Администратор",
  "full_name": "Администратор Системы"
}
```

---

## Patients

### GET /patients
Список пациентов

**Query Parameters:**
- `search` — поиск по ФИО, ИИН, телефону
- `page` — номер страницы (default: 1)
- `limit` — количество на страницу (default: 20, max: 100)

**Response:**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440001",
    "iin": "880312400215",
    "full_name": "Байжанова Айгерим Сериковна",
    "birth_date": "1988-03-12",
    "phone": "+7 (701) 234-56-78",
    "last_study": null,
    "benefit_category": "NONE"
  }
]
```

### GET /patients/{id}
Карточка пациента

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440001",
  "iin": "880312400215",
  "last_name": "Байжанова",
  "first_name": "Айгерим",
  "middle_name": "Сериковна",
  "birth_date": "1988-03-12",
  "gender": "F",
  "phone": "+7 (701) 234-56-78",
  "email": null,
  "benefit_category": "NONE",
  "document_type": null,
  "document_number": null,
  "notes": null,
  "created_at": "2024-01-15T09:30:00",
  "updated_at": "2024-01-15T09:30:00"
}
```

### POST /patients
Создать пациента

**Request:**
```json
{
  "iin": "880312400215",
  "last_name": "Байжанова",
  "first_name": "Айгерим",
  "middle_name": "Сериковна",
  "birth_date": "1988-03-12",
  "gender": "F",
  "phone": "+7 (701) 234-56-78",
  "benefit_category": "NONE",
  "notes": "Аллергия на йодный контраст"
}
```

### PUT /patients/{id}
Обновить пациента

**Request:**
```json
{
  "phone": "+7 (777) 123-45-67",
  "notes": "Обновленная информация"
}
```

---

## Orders (Направления)

### GET /orders
Список направлений

**Query Parameters:**
- `status` — фильтр по статусу
- `patient_id` — фильтр по пациенту
- `page` — номер страницы
- `limit` — количество на страницу

### GET /orders/{id}
Детали направления

### POST /orders
Создать направление

**Request:**
```json
{
  "patient_id": "550e8400-e29b-41d4-a716-446655440001",
  "service_id": "550e8400-e29b-41d4-a716-446655440010",
  "modality": "MR",
  "body_part": "Головной мозг",
  "priority": "ROUTINE",
  "financing_type": "PAID",
  "referring_physician_name": "Османов Н.Т.",
  "clinical_notes": "Головные боли, головокружения",
  "contrast_agent": false
}
```

### PUT /orders/{id}/status
Обновить статус

**Request:**
```json
{
  "status": "SCHEDULED",
  "reason": null
}
```

---

## Reports (Заключения)

### GET /reports
Список заключений

### POST /reports
Создать черновик

**Request:**
```json
{
  "order_id": "550e8400-e29b-41d4-a716-446655440020",
  "protocol_template_id": null,
  "structured_fields": {},
  "description_text": "МРТ головного мозга выполнена на аппарате 3.0 Тл...",
  "conclusion_text": "Признаков острого инсульта не выявлено...",
  "critical_finding": false,
  "diagnosis_icd_codes": ["G43.1"]
}
```

### PUT /reports/{id}
Редактировать заключение

### POST /reports/{id}/sign
Подписать заключение (ЭЦП-ready)

### POST /reports/{id}/issue
Выдать заключение пациенту

---

## References (Справочники)

### GET /refs/services
Тарифы (услуги)

**Query Parameters:**
- `modality` — фильтр по модальности (CT, MR, US, CR, MG)
- `search` — поиск по названию или коду

### GET /refs/devices
Аппараты (Modalities)

### GET /refs/icd10
Диагнозы ICD-10

**Query Parameters:**
- `q` — поисковый запрос (код или название)
- `chapter` — фильтр по главе

### GET /refs/protocol-templates
Протокольные шаблоны

---

## Schedule (Расписание)

### GET /schedule/slots
Получить слоты для аппарата

**Query Parameters:**
- `device_id` (required) — ID аппарата
- `date` (required) — дата (YYYY-MM-DD)

### POST /schedule/appointments
Записать на слот

**Request:**
```json
{
  "order_id": "550e8400-e29b-41d4-a716-446655440020",
  "device_id": "550e8400-e29b-41d4-a716-446655440030",
  "slot_start": "2024-01-16T10:00:00",
  "slot_end": "2024-01-16T10:30:00"
}
```

---

## Worklist

### GET /worklist
Список для выполнения

### POST /worklist/{id}/arrived
Отметить прибытие

### POST /worklist/{id}/in-progress
Начать исследование

### POST /worklist/{id}/qc
Контроль качества

**Query Parameters:**
- `status` — ACCEPTED или RETAKE
- `comment` — комментарий

---

## Statistics

### GET /stats/dashboard
Дашборд статистики

**Query Parameters:**
- `period` — today, week, month

**Response:**
```json
{
  "period": "today",
  "total_studies": 45,
  "by_status": { "NEW": 5, "SCHEDULED": 12, "ISSUED": 28 },
  "by_modality": { "CT": 18, "MR": 15, "US": 12 },
  "by_financing": { "PAID": 25, "GOMBP": 15, "OSMS": 5 },
  "avg_tat_hours": 3.2,
  "overdue_count": 2,
  "to_report": 8
}
```

### GET /stats/turnaround
TAT анализ

**Query Parameters:**
- `from` — дата начала (YYYY-MM-DD)
- `to` — дата окончания (YYYY-MM-DD)

---

## Admin

### GET /admin/users
Список пользователей

### POST /admin/users
Создать пользователя

**Request:**
```json
{
  "login": "petrova",
  "password": "securepassword123",
  "first_name": "Мария",
  "last_name": "Петрова",
  "role": "RADIOLOGIST",
  "specialization": "Лучевая диагностика",
  "email": "petrova@ris.kz",
  "is_active": true
}
```

### PUT /admin/users/{id}
Обновить пользователя

### GET /admin/audit
Аудит-лог

**Query Parameters:**
- `entity_type` — тип сущности
- `entity_id` — ID сущности
- `user_id` — ID пользователя
- `page` — номер страницы
- `limit` — количество на страницу
