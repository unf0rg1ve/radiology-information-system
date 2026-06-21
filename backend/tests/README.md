# Backend tests

## Quick start

```bash
cd backend

# 1. Use Python 3.11 (the project is pinned to this version)
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt

# 2. Run the full suite
.venv\Scripts\python -m pytest -v
```

## Test structure

| File | What it covers |
|------|----------------|
| `test_auth_extensions.py` | Login/logout, token refresh, role-based access |
| `test_patients.py` | Patient CRUD, IIN validation, search |
| `test_reports.py` | Report lifecycle, PDF endpoints, datetime handling |
| `test_ris.py` | Core RIS workflows: studies, orders, statuses |
| `test_worklist_resolve.py` | Worklist matching and conflict resolution |
| `test_status_machine.py` | Study/order state transitions |
| `test_accession_number.py` | Accession number generation and uniqueness |
| `test_orthanc_adapter.py` | DICOM/Orthanc adapter integration |
| `test_webhook.py` | Webhook delivery and retries |

## Infrastructure

- The test database `ris_test` is created automatically by `conftest.py` if it does not exist.
- Tests use a fresh async SQLAlchemy session and rollback transactions so the database stays clean.

## Known environment requirements

### WeasyPrint / GTK on Windows

The application uses `weasyprint` to generate PDFs. On Windows the test suite (and the app itself) will fail to import `app.services.pdf` if GTK libraries are missing:

```
OSError: cannot load library 'gobject-2.0-0': error 0x7e
```

To run the full test suite on Windows you need the GTK runtime installed and available on `PATH`:

1. Download and install the GTK3 runtime for Windows (for example via MSYS2: `mingw-w64-x86_64-gtk3`).
2. Add the directory containing `gobject-2.0-0.dll` to your system/user `PATH`.
3. Restart your terminal and rerun pytest.

Without GTK installed you can still smoke-test imports by mocking `weasyprint` before loading application modules.
