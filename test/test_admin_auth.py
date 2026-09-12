"""Tests for admin authentication: registration (single-admin enforcement),
login, protected-endpoint access, refresh-token rotation, and logout."""

import pytest


async def _register(client, payload):
    return await client.post("/api/v1/auth/admin/register", json=payload)


async def _login(client, email, password):
    return await client.post(
        "/api/v1/auth/admin/login", json={"email": email, "password": password}
    )


class TestAdminRegistration:
    async def test_first_admin_can_be_created(self, client, admin_payload):
        response = await _register(client, admin_payload)
        assert response.status_code == 201
        body = response.json()
        assert body["data"]["email"] == admin_payload["email"]
        assert "hashed_password" not in body["data"]

    async def test_second_admin_registration_is_rejected(self, client, admin_payload):
        first = await _register(client, admin_payload)
        assert first.status_code == 201

        second = await _register(
            client,
            {"username": "someone-else", "email": "other@hethera.ai", "password": "AnotherPass123"},
        )
        assert second.status_code == 409
        assert "already exists" in second.json()["message"]

    async def test_registration_never_stores_plaintext_password(self, client, admin_payload, db_session):
        from sqlalchemy import select

        from app.model.super_admin import SuperAdmin

        await _register(client, admin_payload)
        result = await db_session.execute(select(SuperAdmin))
        admin = result.scalar_one()
        assert admin.hashed_password != admin_payload["password"]
        assert admin.hashed_password.startswith("$2b$")  # bcrypt hash prefix


class TestAdminLogin:
    async def test_login_with_invalid_credentials_is_rejected(self, client, admin_payload):
        await _register(client, admin_payload)
        response = await _login(client, admin_payload["email"], "wrong-password")
        assert response.status_code == 401

    async def test_login_with_unknown_email_is_rejected(self, client, admin_payload):
        await _register(client, admin_payload)
        response = await _login(client, "nobody@hethera.ai", admin_payload["password"])
        assert response.status_code == 401

    async def test_valid_login_returns_access_and_refresh_tokens(self, client, admin_payload):
        await _register(client, admin_payload)
        response = await _login(client, admin_payload["email"], admin_payload["password"])
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["access_token"]
        assert data["refresh_token"]
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0


class TestProtectedEndpoints:
    async def test_protected_endpoint_without_token_is_rejected(self, client):
        response = await client.get("/api/v1/admin/me")
        assert response.status_code == 401

    async def test_protected_endpoint_with_invalid_token_is_rejected(self, client):
        response = await client.get(
            "/api/v1/admin/me", headers={"Authorization": "Bearer not-a-real-token"}
        )
        assert response.status_code == 401

    async def test_protected_endpoint_with_expired_token_is_rejected(self, client, admin_payload):
        import uuid
        from datetime import datetime, timedelta, timezone

        import jwt

        from app.config import app_settings

        register = await _register(client, admin_payload)
        admin_id = register.json()["data"]["id"]

        expired_token = jwt.encode(
            {
                "sub": str(uuid.UUID(admin_id)),
                "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
            },
            app_settings.SECRET_KEY,
            algorithm=app_settings.ALGORITHM,
        )

        response = await client.get(
            "/api/v1/admin/me", headers={"Authorization": f"Bearer {expired_token}"}
        )
        assert response.status_code == 401

    async def test_protected_endpoint_with_valid_token_succeeds(self, client, admin_payload):
        await _register(client, admin_payload)
        login = await _login(client, admin_payload["email"], admin_payload["password"])
        access_token = login.json()["data"]["access_token"]

        response = await client.get(
            "/api/v1/admin/me", headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response.status_code == 200
        assert response.json()["data"]["email"] == admin_payload["email"]


class TestRefreshTokenFlow:
    async def test_refresh_with_valid_token_issues_new_pair(self, client, admin_payload):
        await _register(client, admin_payload)
        login = await _login(client, admin_payload["email"], admin_payload["password"])
        refresh_token = login.json()["data"]["refresh_token"]

        response = await client.post(
            "/api/v1/auth/admin/refresh", json={"refresh_token": refresh_token}
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["access_token"]
        assert data["refresh_token"] != refresh_token

    async def test_refresh_token_is_single_use(self, client, admin_payload):
        """Refresh tokens rotate: reusing a spent one must fail."""
        await _register(client, admin_payload)
        login = await _login(client, admin_payload["email"], admin_payload["password"])
        refresh_token = login.json()["data"]["refresh_token"]

        first = await client.post(
            "/api/v1/auth/admin/refresh", json={"refresh_token": refresh_token}
        )
        assert first.status_code == 200

        second = await client.post(
            "/api/v1/auth/admin/refresh", json={"refresh_token": refresh_token}
        )
        assert second.status_code == 401

    async def test_invalid_refresh_token_is_rejected(self, client):
        response = await client.post(
            "/api/v1/auth/admin/refresh", json={"refresh_token": "garbage-token"}
        )
        assert response.status_code == 401

    async def test_new_access_token_from_refresh_works_on_protected_endpoint(
        self, client, admin_payload
    ):
        await _register(client, admin_payload)
        login = await _login(client, admin_payload["email"], admin_payload["password"])
        refresh_token = login.json()["data"]["refresh_token"]

        refreshed = await client.post(
            "/api/v1/auth/admin/refresh", json={"refresh_token": refresh_token}
        )
        new_access_token = refreshed.json()["data"]["access_token"]

        response = await client.get(
            "/api/v1/admin/me", headers={"Authorization": f"Bearer {new_access_token}"}
        )
        assert response.status_code == 200


class TestLogout:
    async def test_logout_revokes_refresh_token(self, client, admin_payload):
        await _register(client, admin_payload)
        login = await _login(client, admin_payload["email"], admin_payload["password"])
        refresh_token = login.json()["data"]["refresh_token"]

        logout_response = await client.post(
            "/api/v1/auth/admin/logout", json={"refresh_token": refresh_token}
        )
        assert logout_response.status_code == 204

        refresh_response = await client.post(
            "/api/v1/auth/admin/refresh", json={"refresh_token": refresh_token}
        )
        assert refresh_response.status_code == 401

    async def test_logout_with_unknown_token_is_idempotent(self, client):
        response = await client.post(
            "/api/v1/auth/admin/logout", json={"refresh_token": "never-issued"}
        )
        assert response.status_code == 204
