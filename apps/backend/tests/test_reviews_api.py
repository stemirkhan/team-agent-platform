"""Integration tests for review endpoints."""

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


def test_create_and_list_agent_reviews(client: TestClient) -> None:
    """Authenticated user can create review for published agent."""
    owner_headers = _auth_headers(
        client,
        email="agent-owner@example.com",
        display_name="Agent Owner",
    )
    reviewer_headers = _auth_headers(
        client,
        email="agent-reviewer@example.com",
        display_name="Agent Reviewer",
    )

    client.post(
        "/api/v1/agents",
        headers=owner_headers,
        json={
            "slug": "review-agent",
            "title": "Review Agent",
            "short_description": "Published agent used for reviews endpoint tests.",
            "category": "backend",
        },
    )
    client.post("/api/v1/agents/review-agent/publish", headers=owner_headers)

    create_response = client.post(
        "/api/v1/agents/review-agent/reviews",
        headers=reviewer_headers,
        json={
            "rating": 5,
            "text": "Works very well for architecture checks.",
            "works_as_expected": True,
            "outdated_flag": False,
            "unsafe_flag": False,
        },
    )
    assert create_response.status_code == 201
    assert create_response.json()["user_display_name"] == "Agent Reviewer"
    assert create_response.json()["entity_type"] == "agent"

    list_response = client.get("/api/v1/agents/review-agent/reviews")
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["rating"] == 5


def test_duplicate_review_is_rejected(client: TestClient) -> None:
    """User cannot create second review for same entity."""
    owner_headers = _auth_headers(
        client,
        email="dup-owner@example.com",
        display_name="Dup Owner",
    )
    reviewer_headers = _auth_headers(
        client,
        email="dup-reviewer@example.com",
        display_name="Dup Reviewer",
    )

    client.post(
        "/api/v1/agents",
        headers=owner_headers,
        json={
            "slug": "dup-agent",
            "title": "Dup Agent",
            "short_description": "Published agent for duplicate review checks.",
            "category": "backend",
        },
    )
    client.post("/api/v1/agents/dup-agent/publish", headers=owner_headers)

    first_response = client.post(
        "/api/v1/agents/dup-agent/reviews",
        headers=reviewer_headers,
        json={"rating": 4, "text": "Nice."},
    )
    assert first_response.status_code == 201

    second_response = client.post(
        "/api/v1/agents/dup-agent/reviews",
        headers=reviewer_headers,
        json={"rating": 3, "text": "Changed my mind."},
    )
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "User has already reviewed this entity."


def test_create_and_list_team_reviews(client: TestClient) -> None:
    """Authenticated user can create review for published team."""
    owner_headers = _auth_headers(
        client,
        email="team-owner@example.com",
        display_name="Team Owner",
    )
    reviewer_headers = _auth_headers(
        client,
        email="team-reviewer@example.com",
        display_name="Team Reviewer",
    )

    client.post(
        "/api/v1/teams",
        headers=owner_headers,
        json={
            "slug": "review-team",
            "title": "Review Team",
            "description": "Published team used for reviews endpoint tests.",
        },
    )
    client.post("/api/v1/teams/review-team/publish", headers=owner_headers)

    create_response = client.post(
        "/api/v1/teams/review-team/reviews",
        headers=reviewer_headers,
        json={
            "rating": 4,
            "text": "Good composition and role split.",
            "works_as_expected": True,
        },
    )
    assert create_response.status_code == 201
    assert create_response.json()["entity_type"] == "team"

    list_response = client.get("/api/v1/teams/review-team/reviews")
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["rating"] == 4
