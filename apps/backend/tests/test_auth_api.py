"""Integration tests for authentication endpoints."""

import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.core.config import get_settings
from app.services.auth_service import AuthService
from app.models.user import UserRole
from app.repositories.user import UserRepository
from app.schemas.user import UserCreateInternal


def test_register_and_get_me(client: TestClient) -> None:
    """User can register and access protected /me endpoint."""
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@example.com",
            "password": "supersecure123",
            "display_name": "MVP User",
        },
    )
    assert register_response.status_code == 201
    assert register_response.json()["user"]["role"] == "admin"

    token = register_response.json()["access_token"]
    me_response = client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "user@example.com"


def test_login_with_invalid_password_fails(client: TestClient) -> None:
    """Login should reject wrong credentials."""
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "user2@example.com",
            "password": "supersecure123",
            "display_name": "Second User",
        },
    )

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "user2@example.com",
            "password": "wrong-password",
        },
    )
    assert login_response.status_code == 401
    assert login_response.json()["detail"] == "Invalid email or password."


def test_register_duplicate_email_fails(client: TestClient) -> None:
    """Registration should reject duplicate email."""
    payload = {
        "email": "dup@example.com",
        "password": "supersecure123",
        "display_name": "Duplicate",
    }

    first_response = client.post("/api/v1/auth/register", json=payload)
    assert first_response.status_code == 201

    second_response = client.post("/api/v1/auth/register", json=payload)
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "User with this email already exists."


def test_registration_closes_after_owner_when_open_registration_is_disabled(
    client: TestClient,
    monkeypatch,
) -> None:
    """Only the bootstrap owner account can self-register when open registration is disabled."""
    monkeypatch.setenv("ALLOW_OPEN_REGISTRATION", "false")
    get_settings.cache_clear()

    try:
        first_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "owner@example.com",
                "password": "supersecure123",
                "display_name": "Owner",
            },
        )
        assert first_response.status_code == 201
        assert first_response.json()["user"]["role"] == "admin"

        second_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "intruder@example.com",
                "password": "supersecure123",
                "display_name": "Intruder",
            },
        )
        assert second_response.status_code == 403
        assert (
            second_response.json()["detail"]
            == "Self-registration is closed after the owner account is created."
        )
    finally:
        monkeypatch.setenv("ALLOW_OPEN_REGISTRATION", "true")
        get_settings.cache_clear()


def test_owner_resolution_requires_explicit_admin(db_session_factory) -> None:
    """Owner lookup should not silently fall back to the oldest non-admin user."""
    db = db_session_factory()
    try:
        repository = UserRepository(db)
        repository.create(
            UserCreateInternal(
                email="legacy-user@example.com",
                password_hash="hashed",
                display_name="Legacy User",
                role=UserRole.USER,
            )
        )

        assert repository.get_owner() is None
    finally:
        db.close()


def test_operator_access_requires_explicit_admin_role(db_session_factory) -> None:
    """Host-backed operations should depend on admin role, not a single owner id."""
    db = db_session_factory()
    try:
        repository = UserRepository(db)
        first_admin = repository.create(
            UserCreateInternal(
                email="owner@example.com",
                password_hash="hashed",
                display_name="Owner",
                role=UserRole.ADMIN,
            )
        )
        second_admin = repository.create(
            UserCreateInternal(
                email="operator@example.com",
                password_hash="hashed",
                display_name="Operator",
                role=UserRole.ADMIN,
            )
        )
        regular_user = repository.create(
            UserCreateInternal(
                email="user@example.com",
                password_hash="hashed",
                display_name="User",
                role=UserRole.USER,
            )
        )

        service = AuthService(repository, get_settings())

        assert service.get_owner_user().id == first_admin.id
        assert service.ensure_operator(second_admin).id == second_admin.id

        with pytest.raises(HTTPException) as exc_info:
            service.ensure_operator(regular_user)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Only platform admins can use host-backed operations."
    finally:
        db.close()
