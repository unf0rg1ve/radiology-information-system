# Task: RIS MVP Frontend Critical Fixes

## Summary of Changes

### 1. i18next Initialization (COMPLETED)
- Created `src/i18n/index.ts` with proper i18next initialization using react-i18next and ru.json
- Updated `src/main.tsx` to import `./i18n` before App

### 2. Role-Based Menu in AppLayout (COMPLETED)
- Added `ROLE_MENU_ACCESS` mapping for all roles:
  - REGISTRAR: dashboard, patients, orders, schedule, references
  - TECHNOLOGIST: dashboard, worklist
  - RADIOLOGIST: dashboard, reports
  - HEAD: dashboard, reports, references, admin
  - REFERRER: dashboard, patients, orders
  - ADMIN: all items
- Used `useMemo` to filter `allMenuItems` based on `user?.role`
- Menu now dynamically shows only items the user's role allows

### 3. API Client Updates (COMPLETED)
- Added `pdfApi` with `orderPdf` and `reportPdf` (blob responseType)
- Added `reportsApi.newVersion` and `reportsApi.secondOpinion`
- Added `ordersApi.cancel(id, reason)`
- Added `refsApi.importServices(file)` with FormData upload

### 4. IIN Checksum Validation (COMPLETED)
- Implemented Kazakhstan IIN checksum algorithm as `validateIIN` custom validator
- Supports both weight sets (primary: [1-11], secondary: [3,4,5,6,7,8,9,10,11,1,2])
- Replaces simple length check with full checksum validation
- Applied as Form.Item rules validator

### 5. Cancel Order Button (COMPLETED)
- Added cancel modal with reason textarea
- Cancel button shown for statuses: NEW, SCHEDULED, ARRIVED, IN_PROGRESS
- Calls `ordersApi.cancel(id, reason)`
- Added CANCELLED status to STATUS_MAP

### 6. PDF Download Buttons (COMPLETED)
- OrdersPage: DownloadOutlined button triggers `pdfApi.orderPdf(id)`, creates blob URL, triggers download
- ReportsPage: DownloadOutlined button triggers `pdfApi.reportPdf(id)`, same blob download pattern
- ReportsPage also has "Новая версия" and "Второе мнение" buttons for RADIOLOGIST/HEAD/ADMIN roles
