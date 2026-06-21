"""
Test configuration and fixtures for RIS MVP backend tests.

Uses PostgreSQL test database with session-scoped tables and
function-scoped transaction rollback for fast, isolated tests.
"""
import asyncio
import os
import re
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.core.database import Base, get_db
from app.main import app
from app.auth.password import hash_password
from app.models.user import User
from app.models.organization import Organization

# Use PostgreSQL for testing (same server as app, separate database).
# SQLite is incompatible with ARRAY/JSONB types used by Device.working_days etc.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://ris:ris@localhost:5432/ris_test"
)


def _get_default_database_url(url: str) -> str:
    """Return URL pointing to the default 'postgres' maintenance database."""
    return re.sub(r"/[^/]+$", "/postgres", url)


def _to_asyncpg_dsn(sqlalchemy_url: str) -> str:
    """Convert SQLAlchemy asyncpg URL to a DSN asyncpg.connect() accepts."""
    return sqlalchemy_url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def _ensure_test_database_exists():
    """Create the test database if it does not exist yet."""
    import asyncpg
    from asyncpg.exceptions import InvalidCatalogNameError

    dsn = _to_asyncpg_dsn(TEST_DATABASE_URL)
    try:
        conn = await asyncpg.connect(dsn)
        await conn.close()
        return
    except InvalidCatalogNameError:
        pass

    db_name = dsn.rsplit("/", 1)[-1]
    default_url = _to_asyncpg_dsn(_get_default_database_url(TEST_DATABASE_URL))
    conn = await asyncpg.connect(default_url)
    try:
        await conn.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await conn.close()


test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    """Create the test database (if needed) and all tables once per session."""
    await _ensure_test_database_exists()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Test database is disposable; no need to drop tables at session end


@pytest_asyncio.fixture(autouse=True)
async def db_transaction():
    """
    Run each test inside a transaction that rolls back at the end.
    This keeps tables from setup_database clean and makes tests fast.
    """
    async with test_engine.connect() as conn:
        session = AsyncSession(bind=conn, expire_on_commit=False)

        async def override_get_db():
            yield session

        app.dependency_overrides[get_db] = override_get_db

        yield session

        await session.rollback()
        await session.close()
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client():
    """Async HTTP client for testing API endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
def test_db(db_transaction):
    """Get the test database session for the current test."""
    return db_transaction


@pytest_asyncio.fixture
async def test_org(test_db):
    """Create a test organization."""
    org = Organization(
        name_ru="╨в╨╡╤Б╤В╨╛╨▓╨░╤П ╨╛╤А╨│╨░╨╜╨╕╨╖╨░╤Ж╨╕╤П",
        name_kz="╨в╨╡╤Б╤В ╥▒╨╣╤Л╨╝╤Л",
        license_number="╨Ы╨╕╤Ж╨╡╨╜╨╖╨╕╤П ╨Ь╨Ч ╨а╨Ъ тДЦ 12345",
        address="╨│. ╨Р╨╗╨╝╨░╤В╤Л, ╤Г╨╗. ╨в╨╡╤Б╤В╨╛╨▓╨░╤П, 1",
        phone="+7 (727) 111-22-33",
    )
    test_db.add(org)
    await test_db.flush()
    await test_db.refresh(org)
    return org


@pytest_asyncio.fixture
async def test_admin(test_db, test_org):
    """Create a test admin user."""
    user = User(
        org_id=test_org.id,
        login="testadmin",
        password_hash=hash_password("test123"),
        role="ADMIN",
        last_name="╨Р╨┤╨╝╨╕╨╜╨╕╤Б╤В╤А╨░╤В╨╛╤А",
        first_name="╨в╨╡╤Б╤В",
        email="admin@test.kz",
        is_active=True,
    )
    test_db.add(user)
    await test_db.flush()
    await test_db.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_registrar(test_db, test_org):
    """Create a test registrar user."""
    user = User(
        org_id=test_org.id,
        login="testregistrar",
        password_hash=hash_password("test123"),
        role="REGISTRAR",
        last_name="╨а╨╡╨│╨╕╤Б╤В╤А╨░╤В╨╛╤А",
        first_name="╨в╨╡╤Б╤В",
        email="registrar@test.kz",
        is_active=True,
    )
    test_db.add(user)
    await test_db.flush()
    await test_db.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_token(client, test_admin):
    """Get a JWT auth token for the test admin user."""
    response = await client.post("/api/auth/login", json={
        "login": "testadmin",
        "password": "test123",
    })
    if response.status_code == 200:
        return response.json()["access_token"]
    # If login endpoint doesn't work yet, create a token manually
    from app.auth.jwt import create_access_token
    return create_access_token(
        str(test_admin.id), test_admin.login, test_admin.role,
        test_admin.first_name, test_admin.last_name
    )


@pytest_asyncio.fixture
async def auth_headers(auth_token):
    """Get auth headers with Bearer token."""
    return {"Authorization": f"Bearer {auth_token}"}
