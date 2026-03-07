"""Integration tests for export endpoints."""

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


def test_export_published_agent_and_get_job(client: TestClient) -> None:
    """Published agent can be exported and read by creator."""
    headers = _auth_headers(
        client,
        email="agent-exporter@example.com",
        display_name="Agent Exporter",
    )

    client.post(
        "/api/v1/agents",
        headers=headers,
        json={
            "slug": "export-agent",
            "title": "Export Agent",
            "short_description": "Published agent used for export endpoint tests.",
            "category": "backend",
        },
    )
    client.post("/api/v1/agents/export-agent/publish", headers=headers)

    export_response = client.post(
        "/api/v1/exports/agents/export-agent",
        headers=headers,
        json={"runtime_target": "codex"},
    )
    assert export_response.status_code == 201
    payload = export_response.json()
    assert payload["entity_type"] == "agent"
    assert payload["runtime_target"] == "codex"
    assert payload["status"] == "completed"
    assert payload["result_url"] == "/downloads/agent/export-agent/codex.zip"

    job_id = payload["id"]
    get_response = client.get(f"/api/v1/exports/{job_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["id"] == job_id


def test_export_draft_agent_is_rejected(client: TestClient) -> None:
    """Draft agent cannot be exported."""
    headers = _auth_headers(
        client,
        email="draft-exporter@example.com",
        display_name="Draft Exporter",
    )

    client.post(
        "/api/v1/agents",
        headers=headers,
        json={
            "slug": "draft-export-agent",
            "title": "Draft Export Agent",
            "short_description": "Draft agent for export validation.",
            "category": "backend",
        },
    )

    export_response = client.post(
        "/api/v1/exports/agents/draft-export-agent",
        headers=headers,
        json={"runtime_target": "claude_code"},
    )
    assert export_response.status_code == 400
    assert export_response.json()["detail"] == "Only published agents can be exported."


def test_export_published_team_with_items(client: TestClient) -> None:
    """Published team with at least one item can be exported."""
    headers = _auth_headers(
        client,
        email="team-exporter@example.com",
        display_name="Team Exporter",
    )

    client.post(
        "/api/v1/agents",
        headers=headers,
        json={
            "slug": "team-export-agent",
            "title": "Team Export Agent",
            "short_description": "Published agent used in team export tests.",
            "category": "backend",
        },
    )
    client.post("/api/v1/agents/team-export-agent/publish", headers=headers)

    client.post(
        "/api/v1/teams",
        headers=headers,
        json={
            "slug": "team-for-export",
            "title": "Team For Export",
            "description": "Published team that can be exported.",
        },
    )
    client.post(
        "/api/v1/teams/team-for-export/items",
        headers=headers,
        json={"agent_slug": "team-export-agent", "role_name": "reviewer"},
    )
    client.post("/api/v1/teams/team-for-export/publish", headers=headers)

    export_response = client.post(
        "/api/v1/exports/teams/team-for-export",
        headers=headers,
        json={"runtime_target": "opencode"},
    )
    assert export_response.status_code == 201
    payload = export_response.json()
    assert payload["entity_type"] == "team"
    assert payload["status"] == "completed"
    assert payload["result_url"] == "/downloads/team/team-for-export/opencode.zip"


def test_only_creator_can_access_export_job(client: TestClient) -> None:
    """Export jobs are visible only to creator."""
    owner_headers = _auth_headers(
        client,
        email="owner-export@example.com",
        display_name="Owner Export",
    )
    intruder_headers = _auth_headers(
        client,
        email="intruder-export@example.com",
        display_name="Intruder Export",
    )

    client.post(
        "/api/v1/agents",
        headers=owner_headers,
        json={
            "slug": "private-export-agent",
            "title": "Private Export Agent",
            "short_description": "Published agent for export ownership checks.",
            "category": "backend",
        },
    )
    client.post("/api/v1/agents/private-export-agent/publish", headers=owner_headers)

    export_response = client.post(
        "/api/v1/exports/agents/private-export-agent",
        headers=owner_headers,
        json={"runtime_target": "codex"},
    )
    assert export_response.status_code == 201
    job_id = export_response.json()["id"]

    forbidden_response = client.get(f"/api/v1/exports/{job_id}", headers=intruder_headers)
    assert forbidden_response.status_code == 403
    assert forbidden_response.json()["detail"] == "Only the export creator can access this job."
