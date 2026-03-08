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


def _configure_agent(
    client: TestClient,
    *,
    headers: dict[str, str],
    slug: str,
    title: str,
    publish_agent: bool = True,
) -> str:
    """Create an agent and configure its current export profile."""
    create_response = client.post(
        "/api/v1/agents",
        headers=headers,
        json={
            "slug": slug,
            "title": title,
            "short_description": f"{title} short description.",
            "full_description": f"{title} full description.",
            "category": "backend",
        },
    )
    assert create_response.status_code == 201

    update_response = client.patch(
        f"/api/v1/agents/{slug}",
        headers=headers,
        json={
            "manifest_json": {
                "instructions": f"Run {title} checks.",
                "entrypoints": [f"run_{slug.replace('-', '_')}"],
            },
            "export_targets": ["codex", "claude_code", "opencode"],
        },
    )
    assert update_response.status_code == 200

    if publish_agent:
        publish_response = client.post(f"/api/v1/agents/{slug}/publish", headers=headers)
        assert publish_response.status_code == 200

    return slug


def test_manage_draft_team_items_without_version_selection(client: TestClient) -> None:
    """Draft team supports add, update, delete, reorder and publish without version UI."""
    headers = _auth_headers(
        client,
        email="owner@example.com",
        display_name="Team Owner",
    )

    reviewer_slug = _configure_agent(
        client,
        headers=headers,
        slug="api-auditor",
        title="API Auditor",
    )
    reviewer_update = client.patch(
        "/api/v1/agents/api-auditor",
        headers=headers,
        json={
            "manifest_json": {
                "instructions": "Run API Auditor checks with stricter rules.",
                "entrypoints": ["run_api_auditor"],
            },
            "export_targets": ["codex", "claude_code", "opencode"],
        },
    )
    assert reviewer_update.status_code == 200

    architect_slug = _configure_agent(
        client,
        headers=headers,
        slug="schema-architect",
        title="Schema Architect",
    )

    team_payload = {
        "slug": "mvp-backend-team",
        "title": "MVP Backend Team",
        "description": "Core team for backend quality checks.",
    }

    create_team_response = client.post("/api/v1/teams", json=team_payload, headers=headers)
    assert create_team_response.status_code == 201
    assert create_team_response.json()["status"] == "draft"

    update_team_response = client.patch(
        "/api/v1/teams/mvp-backend-team",
        headers=headers,
        json={
            "title": "MVP Backend Team Draft",
            "description": "Draft bundle for backend reviewers.",
        },
    )
    assert update_team_response.status_code == 200
    assert update_team_response.json()["title"] == "MVP Backend Team Draft"

    add_reviewer_response = client.post(
        "/api/v1/teams/mvp-backend-team/items",
        headers=headers,
        json={
            "agent_slug": reviewer_slug,
            "role_name": "reviewer",
            "config_json": {"strict": True},
            "is_required": True,
        },
    )
    assert add_reviewer_response.status_code == 200
    reviewer_item = add_reviewer_response.json()["items"][0]
    assert reviewer_item["agent_slug"] == "api-auditor"
    assert reviewer_item["agent_title"] == "API Auditor"

    add_architect_response = client.post(
        "/api/v1/teams/mvp-backend-team/items",
        headers=headers,
        json={
            "agent_slug": architect_slug,
            "role_name": "architect",
            "order_index": 0,
            "is_required": False,
        },
    )
    assert add_architect_response.status_code == 200
    items = add_architect_response.json()["items"]
    assert [item["role_name"] for item in items] == ["architect", "reviewer"]

    update_item_response = client.patch(
        f"/api/v1/teams/mvp-backend-team/items/{reviewer_item['id']}",
        headers=headers,
        json={
            "agent_slug": reviewer_slug,
            "role_name": "lead-reviewer",
            "order_index": 0,
            "is_required": False,
        },
    )
    assert update_item_response.status_code == 200
    updated_items = update_item_response.json()["items"]
    assert [item["role_name"] for item in updated_items] == ["lead-reviewer", "architect"]
    assert updated_items[0]["is_required"] is False

    architect_item_id = next(
        item["id"] for item in updated_items if item["role_name"] == "architect"
    )
    delete_item_response = client.delete(
        f"/api/v1/teams/mvp-backend-team/items/{architect_item_id}",
        headers=headers,
    )
    assert delete_item_response.status_code == 200
    assert [item["role_name"] for item in delete_item_response.json()["items"]] == [
        "lead-reviewer"
    ]

    publish_response = client.post("/api/v1/teams/mvp-backend-team/publish", headers=headers)
    assert publish_response.status_code == 200
    assert publish_response.json()["status"] == "published"


def test_reject_adding_unpublished_agent_to_team(client: TestClient) -> None:
    """Draft agents cannot be added into a team."""
    headers = _auth_headers(
        client,
        email="builder@example.com",
        display_name="Builder",
    )

    draft_slug = _configure_agent(
        client,
        headers=headers,
        slug="draft-agent",
        title="Draft Agent",
        publish_agent=False,
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
        json={
            "agent_slug": draft_slug,
            "role_name": "reviewer",
        },
        headers=headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Only published agents can be added to a team."


def test_publish_validations_reject_empty_team_and_duplicate_roles(client: TestClient) -> None:
    """Draft teams must be non-empty and use unique role names before publish."""
    headers = _auth_headers(
        client,
        email="validation-owner@example.com",
        display_name="Validation Owner",
    )

    first_slug = _configure_agent(
        client,
        headers=headers,
        slug="quality-reviewer",
        title="Quality Reviewer",
    )
    second_slug = _configure_agent(
        client,
        headers=headers,
        slug="security-reviewer",
        title="Security Reviewer",
    )

    client.post(
        "/api/v1/teams",
        json={
            "slug": "publish-rules-team",
            "title": "Publish Rules Team",
            "description": "Team to validate publish constraints.",
        },
        headers=headers,
    )

    empty_publish_response = client.post(
        "/api/v1/teams/publish-rules-team/publish",
        headers=headers,
    )
    assert empty_publish_response.status_code == 400
    assert empty_publish_response.json()["detail"] == "Cannot publish empty team."

    first_add_response = client.post(
        "/api/v1/teams/publish-rules-team/items",
        headers=headers,
        json={
            "agent_slug": first_slug,
            "role_name": "reviewer",
        },
    )
    assert first_add_response.status_code == 200

    duplicate_role_response = client.post(
        "/api/v1/teams/publish-rules-team/items",
        headers=headers,
        json={
            "agent_slug": second_slug,
            "role_name": "reviewer",
        },
    )
    assert duplicate_role_response.status_code == 400
    assert duplicate_role_response.json()["detail"] == "Team role names must be unique."


def test_only_owner_can_modify_team(client: TestClient) -> None:
    """Only team owner can edit draft composition and publish."""
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

    agent_slug = _configure_agent(
        client,
        headers=owner_headers,
        slug="shared-agent",
        title="Shared Agent",
    )

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
        json={
            "agent_slug": agent_slug,
            "role_name": "reviewer",
        },
        headers=intruder_headers,
    )
    assert add_item_response.status_code == 403
    assert add_item_response.json()["detail"] == "Only the author can modify this team."

    owner_add_response = client.post(
        "/api/v1/teams/owner-team/items",
        json={
            "agent_slug": agent_slug,
            "role_name": "reviewer",
        },
        headers=owner_headers,
    )
    assert owner_add_response.status_code == 200
    item_id = owner_add_response.json()["items"][0]["id"]

    update_team_response = client.patch(
        "/api/v1/teams/owner-team",
        json={"title": "Intruder Attempt"},
        headers=intruder_headers,
    )
    assert update_team_response.status_code == 403
    assert update_team_response.json()["detail"] == "Only the author can modify this team."

    update_item_response = client.patch(
        f"/api/v1/teams/owner-team/items/{item_id}",
        json={"role_name": "intruder-reviewer"},
        headers=intruder_headers,
    )
    assert update_item_response.status_code == 403
    assert update_item_response.json()["detail"] == "Only the author can modify this team."

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

    published_slug = _configure_agent(
        client,
        headers=first_user_headers,
        slug="published-team-agent",
        title="Published Team Agent",
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
    client.post(
        "/api/v1/teams/first-team-published/items",
        json={
            "agent_slug": published_slug,
            "role_name": "reviewer",
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
