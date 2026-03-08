"""Integration tests for agent catalog endpoints."""

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


def test_create_publish_and_list_agent(client: TestClient) -> None:
    """A draft agent becomes visible in catalog after publish."""
    headers = _auth_headers(
        client,
        email="author@example.com",
        display_name="Author One",
    )
    payload = {
        "slug": "fastapi-reviewer",
        "title": "FastAPI Reviewer",
        "short_description": (
            "Inspects backend architecture and endpoint quality for FastAPI services."
        ),
        "full_description": (
            "Looks for router/service/repository boundaries and common API pitfalls."
        ),
        "category": "backend",
    }

    create_response = client.post("/api/v1/agents", json=payload, headers=headers)
    assert create_response.status_code == 201
    assert create_response.json()["status"] == "draft"
    assert create_response.json()["author_name"] == "Author One"

    empty_catalog_response = client.get("/api/v1/agents")
    assert empty_catalog_response.status_code == 200
    assert empty_catalog_response.json()["total"] == 0

    publish_response = client.post("/api/v1/agents/fastapi-reviewer/publish", headers=headers)
    assert publish_response.status_code == 200
    assert publish_response.json()["status"] == "published"

    catalog_response = client.get("/api/v1/agents")
    assert catalog_response.status_code == 200
    assert catalog_response.json()["total"] == 1

    details_response = client.get("/api/v1/agents/fastapi-reviewer")
    assert details_response.status_code == 200
    assert details_response.json()["slug"] == "fastapi-reviewer"


def test_agent_create_requires_authentication(client: TestClient) -> None:
    """Agent creation endpoint should reject anonymous requests."""
    response = client.post(
        "/api/v1/agents",
        json={
            "slug": "anonymous-agent",
            "title": "Anonymous Agent",
            "short_description": "Attempt to create an agent without authentication should fail.",
            "category": "backend",
        },
    )
    assert response.status_code == 401


def test_only_owner_can_publish_agent(client: TestClient) -> None:
    """Only the author can publish created agent."""
    owner_headers = _auth_headers(
        client,
        email="agent-owner@example.com",
        display_name="Agent Owner",
    )
    intruder_headers = _auth_headers(
        client,
        email="intruder@example.com",
        display_name="Intruder",
    )

    create_response = client.post(
        "/api/v1/agents",
        headers=owner_headers,
        json={
            "slug": "owner-agent",
            "title": "Owner Agent",
            "short_description": "Agent created by owner to verify publish permissions.",
            "category": "backend",
        },
    )
    assert create_response.status_code == 201

    forbidden_response = client.post("/api/v1/agents/owner-agent/publish", headers=intruder_headers)
    assert forbidden_response.status_code == 403
    assert forbidden_response.json()["detail"] == "Only the author can modify this agent."

    publish_response = client.post("/api/v1/agents/owner-agent/publish", headers=owner_headers)
    assert publish_response.status_code == 200
    assert publish_response.json()["status"] == "published"


def test_update_agent_profile_returns_skills_and_markdown_files(client: TestClient) -> None:
    """Agent profile response should expose structured asset attachments."""
    headers = _auth_headers(
        client,
        email="profile-assets@example.com",
        display_name="Profile Assets",
    )

    create_response = client.post(
        "/api/v1/agents",
        headers=headers,
        json={
            "slug": "asset-agent",
            "title": "Asset Agent",
            "short_description": "Agent profile with structured assets.",
            "category": "backend",
        },
    )
    assert create_response.status_code == 201

    profile_response = client.patch(
        "/api/v1/agents/asset-agent",
        headers=headers,
        json={
            "manifest_json": {
                "instructions": "Inspect the repository.",
            },
            "skills": [
                {
                    "slug": "repo-audit",
                    "description": "Repository audit skill.",
                    "content": "# Repo audit\n\nInspect the repository.",
                }
            ],
            "markdown_files": [
                {
                    "path": "AGENTS.md",
                    "content": "# Project instructions\n\nFollow repository rules.",
                }
            ],
        },
    )
    assert profile_response.status_code == 200
    payload = profile_response.json()
    assert payload["skills"] == [
        {
            "slug": "repo-audit",
            "description": "Repository audit skill.",
            "content": "# Repo audit\n\nInspect the repository.",
        }
    ]
    assert payload["markdown_files"] == [
        {
            "path": "AGENTS.md",
            "content": "# Project instructions\n\nFollow repository rules.",
        }
    ]
