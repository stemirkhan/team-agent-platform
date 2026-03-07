"""Integration tests for agent versions API endpoints."""

from fastapi.testclient import TestClient


def _auth_headers(client: TestClient, *, email: str, display_name: str) -> dict[str, str]:
    """Register user and return bearer auth headers."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "supersecure123",
            "display_name": display_name,
        },
    )
    assert response.status_code == 201
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_agent(client: TestClient, *, headers: dict[str, str], slug: str) -> None:
    """Create draft agent for versioning tests."""
    response = client.post(
        "/api/v1/agents",
        headers=headers,
        json={
            "slug": slug,
            "title": "Versioned Agent",
            "short_description": "Agent created to validate version management endpoints.",
            "category": "backend",
        },
    )
    assert response.status_code == 201


def test_create_and_list_agent_versions(client: TestClient) -> None:
    """Creating a new version marks previous release as non-latest."""
    headers = _auth_headers(
        client,
        email="owner-versions@example.com",
        display_name="Owner Versions",
    )
    _create_agent(client, headers=headers, slug="versioned-agent")

    first_version = client.post(
        "/api/v1/agents/versioned-agent/versions",
        headers=headers,
        json={
            "version": "1.0.0",
            "changelog": "Initial stable release.",
            "export_targets": ["codex", "claude_code"],
        },
    )
    assert first_version.status_code == 201
    assert first_version.json()["version"] == "1.0.0"
    assert first_version.json()["is_latest"] is True

    second_version = client.post(
        "/api/v1/agents/versioned-agent/versions",
        headers=headers,
        json={
            "version": "1.1.0",
            "changelog": "Improved review heuristics.",
            "compatibility_matrix": {"codex": ">=0.1.0"},
        },
    )
    assert second_version.status_code == 201
    assert second_version.json()["version"] == "1.1.0"
    assert second_version.json()["is_latest"] is True

    list_response = client.get("/api/v1/agents/versioned-agent/versions")
    assert list_response.status_code == 200
    body = list_response.json()
    assert body["total"] == 2
    assert [item["version"] for item in body["items"]] == ["1.1.0", "1.0.0"]
    assert body["items"][0]["is_latest"] is True
    assert body["items"][1]["is_latest"] is False

    details_response = client.get("/api/v1/agents/versioned-agent/versions/1.0.0")
    assert details_response.status_code == 200
    assert details_response.json()["is_latest"] is False


def test_create_agent_version_requires_owner(client: TestClient) -> None:
    """Only owner can create agent versions."""
    owner_headers = _auth_headers(
        client,
        email="versions-owner@example.com",
        display_name="Versions Owner",
    )
    intruder_headers = _auth_headers(
        client,
        email="versions-intruder@example.com",
        display_name="Versions Intruder",
    )
    _create_agent(client, headers=owner_headers, slug="owner-versioned-agent")

    forbidden_response = client.post(
        "/api/v1/agents/owner-versioned-agent/versions",
        headers=intruder_headers,
        json={"version": "1.0.0"},
    )
    assert forbidden_response.status_code == 403
    assert forbidden_response.json()["detail"] == "Only the author can modify this agent."


def test_duplicate_agent_version_returns_conflict(client: TestClient) -> None:
    """Version value must be unique per agent."""
    headers = _auth_headers(
        client,
        email="duplicate-version-owner@example.com",
        display_name="Duplicate Owner",
    )
    _create_agent(client, headers=headers, slug="duplicate-agent")

    first_response = client.post(
        "/api/v1/agents/duplicate-agent/versions",
        headers=headers,
        json={"version": "2.0.0"},
    )
    assert first_response.status_code == 201

    duplicate_response = client.post(
        "/api/v1/agents/duplicate-agent/versions",
        headers=headers,
        json={"version": "2.0.0"},
    )
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"] == "Agent version already exists."
