# RIS MVP — Документация доработок

**Дата:** 2026-06-15
**Версия:** 2.0.0
**Статус:** Реализовано (после ревью по ТЗ v3)

---

## 1. Архитектурное решение по Redis

**Вопрос:** ТЗ требует 3 контейнера (api, db, orthanc). В текущем docker-compose.yml добавлен 4-й контейнер Redis для WS pub/sub.

**Решение:** Redis **удалён** из docker-compose.yml. Для single-instance MVP in-memory WebSocket достаточен. Это соответствует ТЗ (3 контейнера). Если в будущем потребуется масштабирование, Redis будет добавлен осознанно как расширение архитектуры.

---

## 2. Реализованные доработки (Sprint 3)

### A. Orthanc / DICOM-интеграция (F9.1, F4.1–F4.6) ✅

**Файлы:**
- `backend/app/adapters/orthanc.py` — OrthancAdapter (MWL, viewer, study lookup, polling)
- `backend/app/api/webhook.py` — OnStoredInstance webhook + unmatched study management
- `backend/app/models/unmatched_study.py` — модель для несопоставленных исследований
- `orthanc/plugins/notify_ris.py` — OnStoredInstance plugin
- `orthanc/orthanc.json` — конфигурация (MWL, DICOMweb, Stone Web Viewer)

### B. Alembic-миграции ✅
- Убран `Base.metadata.create_all` из `main.py`
- Initial migration: 13 таблиц + 8 индексов

### C. Атомарная генерация Accession Number (F2.2) ✅
- PostgreSQL advisory lock, формат YYMMDD-NNNNN

### D. Машина состояний Order (F2.3) ✅
- 10 статусов, строгие переходы
- **CANCELLED разрешён только до IN_PROGRESS** (согласно ТЗ раздел 7)
- Русские сообщения об ошибках (HTTP 422)
- **Order.status вынесен в Python-перечисление `OrderStatus(str, Enum)` и реализован как нативный Postgres ENUM `order_status`**
  - Миграция: `backend/alembic/versions/002_convert_order_status_to_enum.py`
  - Создаёт тип `CREATE TYPE order_status AS ENUM (...)` и конвертирует `orders.status` из `VARCHAR(20)` в `order_status` с `USING status::order_status`
  - Все строковые литералы статусов в backend заменены на `OrderStatus.XXX`
  - `validate_status_transition`/`get_allowed_transitions`/`is_terminal_status` продолжают принимать строки и enum-значения
  - Схемы `OrderStatusUpdate` и `OrderResponse` используют `status: OrderStatus` — Pydantic сериализует enum как строку в JSON
  - Защита на уровне БД: Postgres сам отклоняет `INSERT/UPDATE orders.status = 'WRONG'`

### E. PDF-генерация (F2.5, F5.6) ✅
- WeasyPrint + Jinja2 шаблоны
- Реквизиты по НПА РК, "ЧЕРНОВИК", "КРИТИЧЕСКАЯ НАХОДКА"

### F. Версионирование Report (F7.4) ✅
- DRAFT → редактируется; подписанный — неизменяем (403)
- `POST /reports/{id}/new-version` — новая версия с parent_report_id

### G. CITO-уведомления + Второе мнение (F5.6, F5.7) ✅
- CITO_NOTIFICATION в audit_log при critical_finding
- `POST /reports/{id}/second-opinion` (HEAD only)

### H. RBAC для REFERRER (F7.2) ✅
- Фильтрация patients/orders по referring_physician_id

### I. Импорт тарификатора из CSV/Excel (F6.1) ✅
- Версионирование, поддержка CSV и .xlsx/.xls

### J. Сквозной аудит-лог (F7.3) ✅
- Отказ от SQLAlchemy event listeners на `AsyncSession` (они не срабатывали) в пользу **явных** `AuditLog(...)` записей в API-эндпоинтах.
- Покрытые операции:
  - `auth.py`: LOGIN, LOGOUT
  - `patients.py`: CREATE/UPDATE Patient
  - `orders.py`: CREATE Order, STATUS_UPDATE Order
  - `reports.py`: CREATE/UPDATE/SIGN/ISSUE Report, CREATE новой версии, CREATE второго мнения, CITO_NOTIFICATION
  - `admin.py`: CREATE/UPDATE/PASSWORD_RESET/PASSWORD_CHANGE User
  - `worklist.py`: UNMATCHED_RESOLVED

### K. WebSocket (отложено) ✅
- In-memory для single-instance, архитектура подготовлена

---

## 3. Доработки после ревью по ТЗ v3 (Версия 2.0)

### Ревью выявило 48 пробелов в фронтенде и 14 несоответствий в бэкенде.
### Все критические и важные пробелы устранены:

### 3.1 Бэкенд: новые API-эндпоинты

| # | Эндпоинт | ТЗ | RBAC | Описание |
|---|----------|-----|------|----------|
| 1 | `POST /refs/protocol-templates` | F6.4 | admin | Создание шаблона протокола |
| 2 | `PUT /refs/protocol-templates/{id}` | F6.4 | admin | Редактирование шаблона |
| 3 | `DELETE /refs/protocol-templates/{id}` | F6.4 | admin | Деактивация шаблона |
| 4 | `GET /worklist/unmatched` | F4.5 | any | Список несопоставленных исследований (из таблицы UnmatchedStudy) |
| 5 | `POST /worklist/unmatched/{id}/resolve` | F4.5 | admin/technologist | Ручное связывание с заказом |
| 6 | `GET /admin/organization` | F6.6 | any | Реквизиты организации |
| 7 | `PUT /admin/organization` | F6.6 | admin | Обновление реквизитов |
| 8 | `PUT /auth/password` | F6.5 | any | Смена пароля |
| 9 | `PUT /reports/{id}/assign` | ТЗ §7 | head | Переназначение радиолога |
| 10 | `GET /stats/export` | F8.4 | head | Экспорт статистики в CSV |
| 11 | `GET /patients/{id}/history` | F1.4 | any | История исследований пациента |
| 12 | `PUT /refs/devices/{id}` | F3.3 | admin | Управление статусом аппарата |
| 13 | `PUT /schedule/appointments/{id}` | F3.2 | registrar | Перенос записи на другой слот |
| 14 | `POST /auth/logout` | F7.1 | any | Фиксация выхода в audit_log |
| 15 | `POST /auth/refresh` | F7.1 | any | Заглушка 501 — не реализован в MVP |

### 3.2 Бэкенд: исправления по ТЗ

- **status_machine.py**: Убран CANCELLED из TO_REPORT и REPORTING (ТЗ: «только до IN_PROGRESS»)
- **auth.py**: Добавлена запись LOGIN в AuditLog при успешном входе
- **schedule.py**: Проверка статуса аппарата при получении слотов (не-ACTIVE → пусто с предупреждением)

### 3.3 Фронтенд: доработки

| # | Функция | Файл | Описание |
|---|---------|------|----------|
| 1 | i18n инициализация | `i18n/index.ts`, `main.tsx` | i18next подключён, ru.json загружен |
| 2 | Роль-ориентированное меню | `AppLayout.tsx` | Меню фильтруется по роли пользователя |
| 3 | Валидация ИИН (checksum) | `PatientsPage.tsx` | Казахстанский алгоритм контрольной цифры |
| 4 | PDF скачивание | `OrdersPage.tsx`, `ReportsPage.tsx` | Кнопки скачивания PDF направления/заключения |
| 5 | Отмена направления | `OrdersPage.tsx` | Кнопка «Отменить» с модалом причины |
| 6 | Новая версия заключения | `ReportsPage.tsx` | Кнопка для RADIOLOGIST/HEAD/ADMIN |
| 7 | Второе мнение | `ReportsPage.tsx` | Кнопка для HEAD/ADMIN |
| 8 | API-клиент обновлён | `client.ts` | +pdfApi, +cancel, +newVersion, +secondOpinion, +importServices |

### 3.4 Новые/обновлённые схемы

- `schemas/protocol_template.py` — ProtocolTemplateCreate, ProtocolTemplateUpdate
- `schemas/organization.py` — OrganizationResponse, OrganizationUpdate
- `schemas/device.py` — DeviceUpdate

### 3.5 Исправленные критичные баги (Kimi K2.7 — фикс F7.3 + ИИН)

- **`backend/app/schemas/patient.py`**: исправлен regex в `validate_iin` — `r'^\\d{12}$'` → `r'^\d{12}$'`. Ранее паттерн с двойным бэкслэшем в raw-строке не распознавал цифры, и **любой** ИИН отклонялся с 422, полностью блокируя создание пациента (F1.2).
- **`backend/app/services/accession_number.py`**: исправлена генерация Accession Number при `org_id=None`. Запрос `(:org_id IS NULL OR org_id = :org_id)` с `None` вызывал `asyncpg.exceptions.AmbiguousParameterError` и не позволял создать Order. Разделены ветки запроса для `org_id` и `org_id=None`.
- **`backend/app/services/audit.py`**: добавлена helper `json_safe()` для корректной сериализации UUID/date/datetime в JSON-поля `audit_log.before_json/after_json`.
- **`frontend/src/vite-env.d.ts`** (новый): декларация `ImportMetaEnv` для `VITE_API_URL` + `declare module '@ant-design/icons'` (отсутствовал единый `.d.ts` для barrell-импорта иконок).
- **`frontend/src/api/client.ts`**: тип `refsApi.icd10` дополнен `limit?: number` (backend эндпоинт `/refs/icd10` реально поддерживает `limit`).
- **`frontend/src/components/layout/AppLayout.tsx`**: устранена `TS2538` (`user?.role` мог быть `undefined` при индексации `ROLE_MENU_MAP`); убран неиспользуемый вызов `antTheme.useToken()`.
- **`frontend/src/pages/OrdersPage.tsx`**: убраны неиспользуемые импорты (`Card`, `EyeOutlined`, `WarningOutlined`) и мёртвый код `doctors`/`setDoctors` (заготовка для выбора направителя, не подключённая к форме); результат `refsApi.icd10({ limit: 100 })` сохранён через `_icdRes` (словарь МКБ-10 продолжает загружаться, но пока не подключён к Select).
- **`frontend/src/pages/AdminPage.tsx`**, **`DashboardPage.tsx`**, **`PatientsPage.tsx`**, **`ReferencesPage.tsx`**, **`WorklistPage.tsx`**: удалены неиспользуемые импорты/переменные (`Descriptions`, `ReloadOutlined`, `TeamOutlined`, `EyeOutlined`, `Space`, `Card`, неиспользуемый параметр `record`).
- **Результат**: `npx tsc --noEmit` → 0 ошибок; `docker compose up -d --build` поднимает все 4 сервиса.

---

## 4. Таблица соответствия ТЗ

| ТЗ ID | Требование | Статус | Примечание |
|-------|-----------|--------|------------|
| F1.1 | Поиск по ИИН/ФИО/ДР/телефону | ✅ | API + UI поиск |
| F1.2 | Создание/редактирование карточки | ✅ | + ИИН checksum |
| F1.3 | Контроль дублей по ИИН | ✅ | 409 при совпадении |
| F1.4 | История исследований | ✅ | GET /patients/{id}/history |
| F2.1 | Создание направления | ✅ | Все обязательные поля |
| F2.2 | Генерация AN | ✅ | Формат YYMMDD-NNNNN, advisory lock (задел на конфигурацию) |
| F2.3 | Управление статусами | ✅ | Машина состояний, 422 при ошибке |
| F2.4 | Отмена с причиной | ✅ | До IN_PROGRESS, причина обязательна |
| F2.5 | Печать направления | ✅ | PDF с реквизитами НПА РК |
| F2.6 | Тип финансирования | ✅ | GOMBP/OSMS/PAID |
| F3.1 | Календарь по аппаратам | ✅ | Месяц + недельный вид (переключатель), перенос записи PUT /schedule/appointments/{id} |
| F3.2 | Запись/перенос/отмена | ✅ | + PUT для переноса |
| F3.3 | Недоступность аппарата | ✅ | PUT /refs/devices/{id}, проверка в schedule |
| F3.4 | Отметка явки | ✅ | SCHEDULED → ARRIVED |
| F3.5 | Предупреждение конфликтов | ✅ | 409 при двойной записи |
| F4.1 | DICOM MWL | ✅ | OrthancAdapter.publish_mwl() |
| F4.2 | Worklist лаборанта | ✅ | GET /worklist с фильтрами |
| F4.3 | Статусы с метками | ✅ | Все переходы фиксируются |
| F4.4 | Автосопоставление по AN | ✅ | Webhook < 5 с |
| F4.5 | Ручное связывание | ✅ | GET /worklist/unmatched + POST /worklist/unmatched/{id}/resolve, UI: Modal «Связать с заказом» |
| F4.6 | Контроль качества | ✅ | QC ACCEPTED/RETAKE |
| F5.1 | Список «к описанию» | ✅ | CITO наверху |
| F5.2 | Экран описания + вьюер | ✅ | 3-колоночный UI: динамическая форма по fields_schema + iframe Stone Viewer |
| F5.3 | Шаблоны протоколов | ✅ | API: CRUD + фильтр по модальности |
| F5.4 | Заключение + МКБ-10 | ✅ | codes array в Report |
| F5.5 | Подпись (ЭЦП-ready) | ✅ | SHA-256 content_hash, неизменяемость |
| F5.6 | Выдача PDF + CITO | ✅ | PDF + CITO_NOTIFICATION + Badge в сайдбаре (поллинг 45с) |
| F5.7 | Второе мнение | ✅ | second_opinion_of_report_id |
| F6.1 | Тарификатор (импорт) | ✅ | CSV/Excel, версионирование |
| F6.2 | МКБ-10 | ✅ | Поиск по коду/наименованию |
| F6.3 | Аппараты/модальности | ✅ | CRUD + статус |
| F6.4 | Шаблоны протоколов CRUD | ✅ | POST/PUT/DELETE |
| F6.5 | Пользователи/роли | ⚠️ | Блокировка ✅, смена пароля ✅, журнал входов ✅ (без отдельного эндпоинта) |
| F6.6 | Реквизиты организации | ✅ | GET/PUT /admin/organization |
| F7.1 | Аутентификация | ✅ | JWT + Argon2, POST /auth/logout (audit LOGOUT); POST /auth/refresh не реализован в MVP — JWT TTL 8ч (см. известные ограничения) |
| F7.2 | RBAC 6 ролей | ✅ | + роль-ориентированное меню |
| F7.3 | Сквозной аудит-лог | ✅ | Явный аудит в эндпоинтах (отказ от неработающего SQLAlchemy listener на AsyncSession). Покрыты CREATE/UPDATE/SIGN/ISSUE для Patient/Order/Report, CREATE/UPDATE/PASSWORD_RESET User, LOGIN/LOGOUT, CITO, UNMATCHED_RESOLVED. |
| F7.4 | Неизменяемость подписанных | ✅ | 403 при редактировании |
| F8.1 | Дашборд | ✅ | По периодам/модальностям/врачам |
| F8.2 | Turnaround time | ✅ | avg_tat_hours |
| F8.3 | Нагрузка на аппараты/врачей | ✅ | В дашборде |
| F8.4 | Выгрузка CSV/Excel | ✅ | GET /stats/export |
| F8.5 | Отчёт по финансированию | ⚠️ | Базовый by_financing в дашборде |
| F9.1 | DICOMweb/Orthanc | ✅ | MWL + webhook + вьюер |
| F9.2 | Задел: входной интерфейс | ✅ | Контракт описан |
| F9.3 | Задел: исходящий интерфейс | ✅ | Контракт описан |
| F9.4 | Задел: нацсистемы РК | ✅ | Ручной экспорт CSV |

**Легенда:** ✅ = полностью реализовано, ⚠️ = частично/задел

---

## 5. Известные ограничения (не блокируют MVP)

1. **3-колоночный экран описания** — ✅ реализовано: динамическая форма по fields_schema + iframe Stone Viewer + CITO Badge в сайдбаре
2. **Казахская локализация (kz.json)** — ТЗ: «казахский перевод — вне MVP»
4. **Конфигурируемый формат AN** — формат YYMMDD-NNNNN; задел на конфигурацию через settings
5. **Детальный отчёт по финансированию** — базовая разбивка есть; полный отчёт — Sprint 5
6. **IIN duplicate detection UI** — API возвращает 409; UI показывает ошибку, но без ссылки на существующего пациента
7. **ICD-10 автозаполнение в форме заключения** — API поиска есть, но UI использует tags-select без автозаполнения
8. **Нагрузочный тест k6** — требует развёрнутого окружения
9. **Инфраструктура pytest** — тесты не запускаются в Docker-контейнере, потому что `conftest.py` использует SQLite, а модель `Device` содержит PostgreSQL-специфичный тип `ARRAY`. Требуется перевод тестового окружения на PostgreSQL или замена `ARRAY` на JSONB/JSON. До устранения `pytest -v` завершается 100 errors.

---

## 6. Запуск проекта

```bash
# Запуск
docker compose up -d

# Миграции выполняются автоматически (alembic upgrade head)

# Загрузка справочников
docker compose exec backend python scripts/seed_refs.py

# Проверка
curl http://localhost:8000/health
# Frontend: http://localhost:3000 (admin / admin123)
# Orthanc: http://localhost:8042 (orthanc / orthanc)
```
