"""Integration tests for team catalog and builder endpoints."""

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


def test_create_team_and_add_published_agent(client: TestClient) -> None:
    """Published agent can be assigned to a team item."""
    headers = _auth_headers(
        client,
        email="owner@example.com",
        display_name="Team Owner",
    )

    agent_payload = {
        "slug": "api-auditor",
        "title": "API Auditor",
        "short_description": "Validates API design and contract consistency for backend services.",
        "full_description": "Checks endpoints, schemas and status-code conventions.",
        "category": "backend",
    }
    client.post("/api/v1/agents", json=agent_payload, headers=headers)
    client.post("/api/v1/agents/api-auditor/publish", headers=headers)

    team_payload = {
        "slug": "mvp-backend-team",
        "title": "MVP Backend Team",
        "description": "Core team for backend quality checks.",
    }

    create_team_response = client.post("/api/v1/teams", json=team_payload, headers=headers)
    assert create_team_response.status_code == 201
    assert create_team_response.json()["status"] == "draft"
    assert create_team_response.json()["author_name"] == "Team Owner"

    add_item_response = client.post(
        "/api/v1/teams/mvp-backend-team/items",
        json={
            "agent_slug": "api-auditor",
            "role_name": "reviewer",
            "config_json": {"strict": True},
            "is_required": True,
        },
        headers=headers,
    )
    assert add_item_response.status_code == 200
    team_details = add_item_response.json()
    assert len(team_details["items"]) == 1
    assert team_details["items"][0]["agent_slug"] == "api-auditor"

    publish_response = client.post("/api/v1/teams/mvp-backend-team/publish", headers=headers)
    assert publish_response.status_code == 200
    assert publish_response.json()["status"] == "published"

    catalog_response = client.get("/api/v1/teams")
    assert catalog_response.status_code == 200
    assert catalog_response.json()["total"] == 1


def test_reject_adding_unpublished_agent_to_team(client: TestClient) -> None:
    """Draft agents cannot be used in a team."""
    headers = _auth_headers(
        client,
        email="builder@example.com",
        display_name="Builder",
    )

    client.post(
        "/api/v1/agents",
        json={
            "slug": "draft-agent",
            "title": "Draft Agent",
            "short_description": "Temporary draft agent for validation behavior checks.",
            "category": "backend",
        },
        headers=headers,
    )

    client.post(
        "/api/v1/teams",
        json={
            "slug": "validation-team",
            "title": "Validation Team",
            "description": "Team to verify status constraints.",
        },
        headers=headers,
    )

    response = client.post(
        "/api/v1/teams/validation-team/items",
        json={"agent_slug": "draft-agent", "role_name": "reviewer"},
        headers=headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Only published agents can be added to a team."


def test_only_owner_can_modify_team(client: TestClient) -> None:
    """Only team owner can add items and publish team."""
    owner_headers = _auth_headers(
        client,
        email="team-owner@example.com",
        display_name="Team Owner",
    )
    intruder_headers = _auth_headers(
        client,
        email="team-intruder@example.com",
        display_name="Team Intruder",
    )

    client.post(
        "/api/v1/agents",
        json={
            "slug": "shared-agent",
            "title": "Shared Agent",
            "short_description": "Published agent used to test team ownership permissions.",
            "category": "backend",
        },
        headers=owner_headers,
    )
    client.post("/api/v1/agents/shared-agent/publish", headers=owner_headers)

    client.post(
        "/api/v1/teams",
        json={
            "slug": "owner-team",
            "title": "Owner Team",
            "description": "Team with restricted owner-only mutations.",
        },
        headers=owner_headers,
    )

    add_item_response = client.post(
        "/api/v1/teams/owner-team/items",
        json={"agent_slug": "shared-agent", "role_name": "reviewer"},
        headers=intruder_headers,
    )
    assert add_item_response.status_code == 403
    assert add_item_response.json()["detail"] == "Only the author can modify this team."

    publish_response = client.post("/api/v1/teams/owner-team/publish", headers=intruder_headers)
    assert publish_response.status_code == 403
    assert publish_response.json()["detail"] == "Only the author can modify this team."


def test_get_my_teams_returns_only_current_user_teams(client: TestClient) -> None:
    """Current user should only see owned teams on /me/teams."""
    first_user_headers = _auth_headers(
        client,
        email="first-user@example.com",
        display_name="First User",
    )
    second_user_headers = _auth_headers(
        client,
        email="second-user@example.com",
        display_name="Second User",
    )

    client.post(
        "/api/v1/teams",
        json={
            "slug": "first-team-draft",
            "title": "First Team Draft",
            "description": "Draft team owned by first user.",
        },
        headers=first_user_headers,
    )
    client.post(
        "/api/v1/teams",
        json={
            "slug": "first-team-published",
            "title": "First Team Published",
            "description": "Published team owned by first user.",
        },
        headers=first_user_headers,
    )
    client.post("/api/v1/teams/first-team-published/publish", headers=first_user_headers)
    client.post(
        "/api/v1/teams",
        json={
            "slug": "second-team",
            "title": "Second Team",
            "description": "Owned by second user.",
        },
        headers=second_user_headers,
    )

    response = client.get("/api/v1/me/teams", headers=first_user_headers)
    assert response.status_code == 200

    payload = response.json()
    assert payload["total"] == 2

    draft_response = client.get("/api/v1/me/teams?status=draft", headers=first_user_headers)
    assert draft_response.status_code == 200
    draft_payload = draft_response.json()
    assert draft_payload["total"] == 1
    assert draft_payload["items"][0]["slug"] == "first-team-draft"
