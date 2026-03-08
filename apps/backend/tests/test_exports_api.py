"""Integration tests for export endpoints."""

from io import BytesIO
from urllib.parse import parse_qs, urlparse
from zipfile import ZipFile

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


def _configure_agent_profile(
    client: TestClient,
    *,
    headers: dict[str, str],
    slug: str,
    export_targets: list[str] | None = None,
    manifest_json: dict[str, object] | None = None,
    compatibility_matrix: dict[str, object] | None = None,
    install_instructions: str | None = None,
    skills: list[dict[str, object]] | None = None,
    markdown_files: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Configure the current hidden agent profile for export adapter tests."""
    response = client.patch(
        f"/api/v1/agents/{slug}",
        headers=headers,
        json={
            "manifest_json": manifest_json
            or {
                "entrypoints": ["review_api_structure"],
                "instructions": "Analyze API quality and design.",
                "tools_required": ["file_read", "shell"],
                "permissions_required": ["read_repo"],
                "tags": ["fastapi", "review"],
                "codex": {
                    "model": "gpt-5.3-codex-spark",
                    "model_reasoning_effort": "high",
                    "sandbox_mode": "read-only",
                    "developer_instructions": "Inspect code and provide implementation hints.",
                },
                "claude": {
                    "description": "Review API quality and architecture.",
                    "prompt": "Inspect the repository and explain architecture concerns.",
                },
                "opencode": {
                    "description": "Review API quality and architecture.",
                    "prompt": "Inspect repository structure and report implementation risks.",
                },
            },
            "compatibility_matrix": compatibility_matrix,
            "export_targets": export_targets,
            "install_instructions": install_instructions,
            "skills": skills,
            "markdown_files": markdown_files,
        },
    )
    assert response.status_code == 200
    return response.json()


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
    _configure_agent_profile(
        client,
        headers=headers,
        slug="export-agent",
        export_targets=["codex", "claude_code"],
    )

    export_response = client.post(
        "/api/v1/exports/agents/export-agent",
        headers=headers,
        json={
            "runtime_target": "codex",
            "codex": {
                "model": "gpt-5.3-codex-spark",
                "model_reasoning_effort": "medium",
                "sandbox_mode": "read-only",
            },
        },
    )
    assert export_response.status_code == 201
    payload = export_response.json()
    assert payload["entity_type"] == "agent"
    assert payload["runtime_target"] == "codex"
    assert payload["status"] == "completed"
    parsed_result_url = urlparse(payload["result_url"])
    assert parsed_result_url.path == "/downloads/agent/export-agent/codex.toml"
    query = parse_qs(parsed_result_url.query)
    assert query["model"] == ["gpt-5.3-codex-spark"]
    assert query["model_reasoning_effort"] == ["medium"]
    assert query["sandbox_mode"] == ["read-only"]

    job_id = payload["id"]
    get_response = client.get(f"/api/v1/exports/{job_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["id"] == job_id

    list_response = client.get("/api/v1/exports/agents/export-agent", headers=headers)
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["total"] == 1
    assert list_payload["items"][0]["id"] == job_id

    download_response = client.get(payload["result_url"])
    assert download_response.status_code == 200
    assert download_response.headers["content-type"].startswith("text/plain")
    assert "attachment;" in download_response.headers["content-disposition"]
    content = download_response.content.decode("utf-8")
    assert 'model = "gpt-5.3-codex-spark"' in content
    assert 'model_reasoning_effort = "medium"' in content
    assert 'sandbox_mode = "read-only"' in content
    assert 'developer_instructions = "Inspect code and provide implementation hints."' in content


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
        json={"runtime_target": "codex"},
    )
    assert export_response.status_code == 400
    assert export_response.json()["detail"] == "Only published agents can be exported."


def test_export_agent_with_skills_and_markdown_files_returns_zip_bundle(client: TestClient) -> None:
    """Single-agent export switches to zip when the agent has attached assets."""
    headers = _auth_headers(
        client,
        email="agent-bundle@example.com",
        display_name="Agent Bundle",
    )

    client.post(
        "/api/v1/agents",
        headers=headers,
        json={
            "slug": "agent-bundle",
            "title": "Agent Bundle",
            "short_description": "Published agent with skill and markdown attachments.",
            "category": "backend",
        },
    )
    client.post("/api/v1/agents/agent-bundle/publish", headers=headers)
    _configure_agent_profile(
        client,
        headers=headers,
        slug="agent-bundle",
        export_targets=["codex"],
        skills=[
            {
                "slug": "backend-audit",
                "description": "Repository audit skill.",
                "content": "# Backend audit\n\nInspect backend boundaries.",
            }
        ],
        markdown_files=[
            {
                "path": "AGENTS.md",
                "content": "# Project instructions\n\nFollow repository rules.",
            }
        ],
    )

    export_response = client.post(
        "/api/v1/exports/agents/agent-bundle",
        headers=headers,
        json={"runtime_target": "codex"},
    )
    assert export_response.status_code == 201
    payload = export_response.json()
    parsed_result_url = urlparse(payload["result_url"])
    assert parsed_result_url.path == "/downloads/agent/agent-bundle/codex.zip"

    download_response = client.get(payload["result_url"])
    assert download_response.status_code == 200
    assert download_response.headers["content-type"].startswith("application/zip")

    with ZipFile(BytesIO(download_response.content)) as archive:
        names = set(archive.namelist())
        assert "agent-bundle.toml" in names
        assert "AGENTS.md" in names
        assert ".codex/skills/backend-audit/SKILL.md" in names
        skill_content = archive.read(".codex/skills/backend-audit/SKILL.md").decode("utf-8")
        assert "# Backend audit" in skill_content


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
    _configure_agent_profile(
        client,
        headers=headers,
        slug="team-export-agent",
        export_targets=["codex"],
    )

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
        json={
            "runtime_target": "codex",
            "codex": {
                "model": "gpt-5.3-codex-spark",
                "model_reasoning_effort": "medium",
                "sandbox_mode": "read-only",
            },
        },
    )
    assert export_response.status_code == 201
    payload = export_response.json()
    assert payload["entity_type"] == "team"
    assert payload["status"] == "completed"
    parsed_result_url = urlparse(payload["result_url"])
    assert parsed_result_url.path == "/downloads/team/team-for-export/codex.zip"
    query = parse_qs(parsed_result_url.query)
    assert query["model"] == ["gpt-5.3-codex-spark"]
    assert query["model_reasoning_effort"] == ["medium"]
    assert query["sandbox_mode"] == ["read-only"]

    list_response = client.get("/api/v1/exports/teams/team-for-export", headers=headers)
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["total"] == 1
    assert list_payload["items"][0]["id"] == payload["id"]

    download_response = client.get(payload["result_url"])
    assert download_response.status_code == 200
    with ZipFile(BytesIO(download_response.content)) as archive:
        names = set(archive.namelist())
        assert ".codex/config.toml" in names
        assert ".codex/agents/reviewer.toml" in names
        assert "canonical.manifest.json" not in names
        config = archive.read(".codex/config.toml").decode("utf-8")
        assert "multi_agent = true" in config
        assert '[agents."reviewer"]' in config
        assert (
            'description = "Team Export Agent: Published agent used in team export tests."'
            in config
        )
        reviewer = archive.read(".codex/agents/reviewer.toml").decode("utf-8")
        assert 'model = "gpt-5.3-codex-spark"' in reviewer
        assert 'sandbox_mode = "read-only"' in reviewer


def test_team_export_includes_namespaced_agent_assets(client: TestClient) -> None:
    """Team bundle should include markdown and skill assets under agent namespaces."""
    headers = _auth_headers(
        client,
        email="team-assets@example.com",
        display_name="Team Assets",
    )

    client.post(
        "/api/v1/agents",
        headers=headers,
        json={
            "slug": "team-assets-agent",
            "title": "Team Assets Agent",
            "short_description": "Published agent with attached bundle files.",
            "category": "backend",
        },
    )
    client.post("/api/v1/agents/team-assets-agent/publish", headers=headers)
    _configure_agent_profile(
        client,
        headers=headers,
        slug="team-assets-agent",
        export_targets=["codex"],
        skills=[
            {
                "slug": "api-check",
                "content": "# API check\n\nReview backend contracts.",
            }
        ],
        markdown_files=[
            {
                "path": "docs/architecture.md",
                "content": "# Architecture\n\nDocument service boundaries.",
            }
        ],
    )

    client.post(
        "/api/v1/teams",
        headers=headers,
        json={
            "slug": "team-assets-export",
            "title": "Team Assets Export",
            "description": "Published team with agent bundle attachments.",
        },
    )
    client.post(
        "/api/v1/teams/team-assets-export/items",
        headers=headers,
        json={"agent_slug": "team-assets-agent", "role_name": "backend-owner"},
    )
    client.post("/api/v1/teams/team-assets-export/publish", headers=headers)

    export_response = client.post(
        "/api/v1/exports/teams/team-assets-export",
        headers=headers,
        json={"runtime_target": "codex"},
    )
    assert export_response.status_code == 201

    download_response = client.get(export_response.json()["result_url"])
    assert download_response.status_code == 200
    with ZipFile(BytesIO(download_response.content)) as archive:
        names = set(archive.namelist())
        assert "agents/team-assets-agent/docs/architecture.md" in names
        assert ".codex/skills/team-assets-agent-api-check/SKILL.md" in names


def test_team_export_uses_current_agent_profile(client: TestClient) -> None:
    """Published team export should reflect the current agent profile."""
    headers = _auth_headers(
        client,
        email="current-profile-export@example.com",
        display_name="Current Profile Export",
    )

    client.post(
        "/api/v1/agents",
        headers=headers,
        json={
            "slug": "current-profile-team-agent",
            "title": "Current Profile Team Agent",
            "short_description": "Published agent used to validate current team exports.",
            "category": "backend",
        },
    )
    client.post("/api/v1/agents/current-profile-team-agent/publish", headers=headers)
    _configure_agent_profile(
        client,
        headers=headers,
        slug="current-profile-team-agent",
        export_targets=["codex"],
        manifest_json={
            "instructions": "Use the initial export manifest.",
            "codex": {
                "model": "gpt-5.3-codex-spark",
                "model_reasoning_effort": "high",
                "sandbox_mode": "read-only",
                "developer_instructions": "Initial export instructions.",
            },
        },
        install_instructions="Initial install instructions.",
    )
    client.post(
        "/api/v1/teams",
        headers=headers,
        json={
            "slug": "current-profile-team-export",
            "title": "Current Profile Team Export",
            "description": "Export should use the current agent profile.",
        },
    )
    client.post(
        "/api/v1/teams/current-profile-team-export/items",
        headers=headers,
        json={
            "agent_slug": "current-profile-team-agent",
            "role_name": "reviewer",
        },
    )
    client.post("/api/v1/teams/current-profile-team-export/publish", headers=headers)

    _configure_agent_profile(
        client,
        headers=headers,
        slug="current-profile-team-agent",
        export_targets=["codex"],
        manifest_json={
            "instructions": "Use the updated export manifest.",
            "codex": {
                "model": "gpt-5.3-codex-spark",
                "model_reasoning_effort": "medium",
                "sandbox_mode": "workspace-write",
                "developer_instructions": "Updated export instructions.",
            },
        },
        install_instructions="Updated install instructions.",
    )

    export_response = client.post(
        "/api/v1/exports/teams/current-profile-team-export",
        headers=headers,
        json={"runtime_target": "codex"},
    )
    assert export_response.status_code == 201

    download_response = client.get(export_response.json()["result_url"])
    assert download_response.status_code == 200
    with ZipFile(BytesIO(download_response.content)) as archive:
        reviewer = archive.read(".codex/agents/reviewer.toml").decode("utf-8")
        assert 'developer_instructions = "Updated export instructions."' in reviewer
        assert 'sandbox_mode = "workspace-write"' in reviewer


def test_export_published_agent_for_claude_code(client: TestClient) -> None:
    """Published agent can be exported as native Claude Code Markdown."""
    headers = _auth_headers(
        client,
        email="claude-agent@example.com",
        display_name="Claude Agent",
    )

    client.post(
        "/api/v1/agents",
        headers=headers,
        json={
            "slug": "claude-export-agent",
            "title": "Claude Export Agent",
            "short_description": "Published agent used for Claude Code export tests.",
            "category": "backend",
        },
    )
    client.post("/api/v1/agents/claude-export-agent/publish", headers=headers)
    _configure_agent_profile(
        client,
        headers=headers,
        slug="claude-export-agent",
        export_targets=["codex", "claude_code"],
    )

    export_response = client.post(
        "/api/v1/exports/agents/claude-export-agent",
        headers=headers,
        json={
            "runtime_target": "claude_code",
            "claude": {
                "model": "sonnet",
                "permissionMode": "plan",
            },
        },
    )
    assert export_response.status_code == 201
    payload = export_response.json()
    parsed_result_url = urlparse(payload["result_url"])
    assert parsed_result_url.path == "/downloads/agent/claude-export-agent/claude_code.md"
    query = parse_qs(parsed_result_url.query)
    assert query["model"] == ["sonnet"]
    assert query["permissionMode"] == ["plan"]

    download_response = client.get(payload["result_url"])
    assert download_response.status_code == 200
    content = download_response.content.decode("utf-8")
    assert 'name: "claude-export-agent"' in content
    assert 'model: "sonnet"' in content
    assert 'permissionMode: "plan"' in content
    assert "Inspect the repository and explain architecture concerns." in content


def test_export_published_team_for_claude_code(client: TestClient) -> None:
    """Published team can be exported as native Claude Code bundle."""
    headers = _auth_headers(
        client,
        email="claude-team@example.com",
        display_name="Claude Team",
    )

    client.post(
        "/api/v1/agents",
        headers=headers,
        json={
            "slug": "claude-team-agent",
            "title": "Claude Team Agent",
            "short_description": "Published agent used in Claude team export tests.",
            "category": "backend",
        },
    )
    client.post("/api/v1/agents/claude-team-agent/publish", headers=headers)
    _configure_agent_profile(
        client,
        headers=headers,
        slug="claude-team-agent",
        export_targets=["claude_code"],
    )

    client.post(
        "/api/v1/teams",
        headers=headers,
        json={
            "slug": "claude-team-export",
            "title": "Claude Team Export",
            "description": "Published team that can be exported to Claude Code.",
        },
    )
    client.post(
        "/api/v1/teams/claude-team-export/items",
        headers=headers,
        json={
            "agent_slug": "claude-team-agent",
            "role_name": "architect reviewer",
        },
    )
    client.post("/api/v1/teams/claude-team-export/publish", headers=headers)

    export_response = client.post(
        "/api/v1/exports/teams/claude-team-export",
        headers=headers,
        json={
            "runtime_target": "claude_code",
            "claude": {
                "model": "opus",
                "permissionMode": "acceptEdits",
            },
        },
    )
    assert export_response.status_code == 201
    payload = export_response.json()
    parsed_result_url = urlparse(payload["result_url"])
    assert parsed_result_url.path == "/downloads/team/claude-team-export/claude_code.zip"
    query = parse_qs(parsed_result_url.query)
    assert query["model"] == ["opus"]
    assert query["permissionMode"] == ["acceptEdits"]

    download_response = client.get(payload["result_url"])
    assert download_response.status_code == 200
    with ZipFile(BytesIO(download_response.content)) as archive:
        names = set(archive.namelist())
        assert ".claude/agents/architect-reviewer.md" in names
        assert ".codex/config.toml" not in names
        content = archive.read(".claude/agents/architect-reviewer.md").decode("utf-8")
        assert 'name: "architect-reviewer"' in content
        assert 'model: "opus"' in content
        assert 'permissionMode: "acceptEdits"' in content


def test_export_published_agent_for_opencode(client: TestClient) -> None:
    """Published agent can be exported as native OpenCode Markdown."""
    headers = _auth_headers(
        client,
        email="opencode-agent@example.com",
        display_name="OpenCode Agent",
    )

    client.post(
        "/api/v1/agents",
        headers=headers,
        json={
            "slug": "opencode-export-agent",
            "title": "OpenCode Export Agent",
            "short_description": "Published agent used for OpenCode export tests.",
            "category": "backend",
        },
    )
    client.post("/api/v1/agents/opencode-export-agent/publish", headers=headers)
    _configure_agent_profile(
        client,
        headers=headers,
        slug="opencode-export-agent",
        export_targets=["opencode"],
    )

    export_response = client.post(
        "/api/v1/exports/agents/opencode-export-agent",
        headers=headers,
        json={
            "runtime_target": "opencode",
            "opencode": {
                "model": "openai/gpt-5",
                "permission": "allow",
            },
        },
    )
    assert export_response.status_code == 201
    payload = export_response.json()
    parsed_result_url = urlparse(payload["result_url"])
    assert parsed_result_url.path == "/downloads/agent/opencode-export-agent/opencode.md"
    query = parse_qs(parsed_result_url.query)
    assert query["model"] == ["openai/gpt-5"]
    assert query["permission"] == ["allow"]

    download_response = client.get(payload["result_url"])
    assert download_response.status_code == 200
    content = download_response.content.decode("utf-8")
    assert 'description: "Review API quality and architecture."' in content
    assert 'mode: "subagent"' in content
    assert 'model: "openai/gpt-5"' in content
    assert 'permission: "allow"' in content
    assert "Inspect repository structure and report implementation risks." in content


def test_export_published_team_for_opencode(client: TestClient) -> None:
    """Published team can be exported as native OpenCode bundle."""
    headers = _auth_headers(
        client,
        email="opencode-team@example.com",
        display_name="OpenCode Team",
    )

    client.post(
        "/api/v1/agents",
        headers=headers,
        json={
            "slug": "opencode-team-agent",
            "title": "OpenCode Team Agent",
            "short_description": "Published agent used in OpenCode team export tests.",
            "category": "backend",
        },
    )
    client.post("/api/v1/agents/opencode-team-agent/publish", headers=headers)
    _configure_agent_profile(
        client,
        headers=headers,
        slug="opencode-team-agent",
        export_targets=["opencode"],
    )

    client.post(
        "/api/v1/teams",
        headers=headers,
        json={
            "slug": "opencode-team-export",
            "title": "OpenCode Team Export",
            "description": "Published team that can be exported to OpenCode.",
        },
    )
    client.post(
        "/api/v1/teams/opencode-team-export/items",
        headers=headers,
        json={
            "agent_slug": "opencode-team-agent",
            "role_name": "risk reviewer",
        },
    )
    client.post("/api/v1/teams/opencode-team-export/publish", headers=headers)

    export_response = client.post(
        "/api/v1/exports/teams/opencode-team-export",
        headers=headers,
        json={
            "runtime_target": "opencode",
            "opencode": {
                "model": "anthropic/claude-sonnet-4.5",
                "permission": "ask",
            },
        },
    )
    assert export_response.status_code == 201
    payload = export_response.json()
    parsed_result_url = urlparse(payload["result_url"])
    assert parsed_result_url.path == "/downloads/team/opencode-team-export/opencode.zip"
    query = parse_qs(parsed_result_url.query)
    assert query["model"] == ["anthropic/claude-sonnet-4.5"]
    assert query["permission"] == ["ask"]

    download_response = client.get(payload["result_url"])
    assert download_response.status_code == 200
    with ZipFile(BytesIO(download_response.content)) as archive:
        names = set(archive.namelist())
        assert ".opencode/agents/risk-reviewer.md" in names
        assert ".claude/agents/architect-reviewer.md" not in names
        content = archive.read(".opencode/agents/risk-reviewer.md").decode("utf-8")
        assert 'mode: "subagent"' in content
        assert 'model: "anthropic/claude-sonnet-4.5"' in content
        assert 'permission: "ask"' in content


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
    _configure_agent_profile(
        client,
        headers=owner_headers,
        slug="private-export-agent",
        export_targets=["codex"],
    )

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


def test_export_uses_default_profile_for_published_agent(client: TestClient) -> None:
    """Published agent should export even without manual profile updates."""
    headers = _auth_headers(
        client,
        email="default-profile@example.com",
        display_name="Default Profile",
    )

    client.post(
        "/api/v1/agents",
        headers=headers,
        json={
            "slug": "default-profile-agent",
            "title": "Default Profile Agent",
            "short_description": "Published agent without manual profile setup.",
            "category": "backend",
        },
    )
    client.post("/api/v1/agents/default-profile-agent/publish", headers=headers)

    export_response = client.post(
        "/api/v1/exports/agents/default-profile-agent",
        headers=headers,
        json={"runtime_target": "codex"},
    )
    assert export_response.status_code == 201

    download_response = client.get(export_response.json()["result_url"])
    assert download_response.status_code == 200
    content = download_response.content.decode("utf-8")
    assert 'description = "Published agent without manual profile setup."' in content
    assert (
        'developer_instructions = "Published agent without manual profile setup."' in content
    )


def test_export_rejects_runtime_not_in_export_targets(client: TestClient) -> None:
    """Export should fail when runtime is not allowed by the current profile."""
    headers = _auth_headers(
        client,
        email="runtime-filter@example.com",
        display_name="Runtime Filter",
    )

    client.post(
        "/api/v1/agents",
        headers=headers,
        json={
            "slug": "runtime-limited-agent",
            "title": "Runtime Limited Agent",
            "short_description": "Agent with restricted export targets.",
            "category": "backend",
        },
    )
    client.post("/api/v1/agents/runtime-limited-agent/publish", headers=headers)
    _configure_agent_profile(
        client,
        headers=headers,
        slug="runtime-limited-agent",
        export_targets=["codex"],
    )

    response = client.post(
        "/api/v1/exports/agents/runtime-limited-agent",
        headers=headers,
        json={"runtime_target": "claude_code"},
    )
    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Agent 'runtime-limited-agent' does not support runtime 'claude_code'."
    )
