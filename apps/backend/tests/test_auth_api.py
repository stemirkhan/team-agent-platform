"""Integration tests for authentication endpoints."""

from fastapi.testclient import TestClient


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
