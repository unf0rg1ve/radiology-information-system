"""
Tests for auth endpoints (F7.1): logout and refresh placeholder.
"""
import pytest
from datetime import datetime
from uuid import uuid4


class TestAuthLogout:

    @pytest.mark.asyncio
    async def test_logout_creates_audit_record(self, client, test_db):
        from app.models.user import User
        from app.models.organization import Organization
        from app.models.audit_log import AuditLog
        from app.auth.jwt import create_access_token

        org = Organization(name_ru="Logout Org", name_kz="", license_number="", address="", phone="")
        test_db.add(org)
        await test_db.flush()

        user = User(
            org_id=org.id,
            login="logout_user",
            password_hash="x",
            role="ADMIN",
            last_name="Logout",
            first_name="User",
            is_active=True,
        )
        test_db.add(user)
        await test_db.flush()

        token = create_access_token(str(user.id), user.login, user.role, user.first_name, user.last_name)

        response = await client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        result = await test_db.execute(
            AuditLog.__table__.select().where(
                AuditLog.entity_id == user.id,
                AuditLog.action == "LOGOUT",
            )
        )
        audit = result.fetchone()
        assert audit is not None

    @pytest.mark.asyncio
    async def test_logout_requires_auth(self, client):
        response = await client.post("/api/auth/logout")
        assert response.status_code == 403


class TestAuthRefresh:

    @pytest.mark.asyncio
    async def test_refresh_returns_501_not_implemented(self, client):
        response = await client.post("/api/auth/refresh")
        assert response.status_code == 501
        assert "не реализованы" in response.json()["detail"].lower() or "MVP" in response.json()["detail"]