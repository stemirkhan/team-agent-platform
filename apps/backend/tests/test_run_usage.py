"""Focused tests for run token-usage enrichment."""

from types import SimpleNamespace

from app.schemas.codex import CodexSessionRead
from app.schemas.run import RunRead
from app.services.run_service import RunService


def test_enrich_run_for_read_attaches_session_usage_without_turn_completed() -> None:
    """Completed-session usage should be exposed on the run read model."""
    run = SimpleNamespace(
        id="run-1",
        workspace_id="ws-1",
        input_tokens=None,
        output_tokens=None,
    )
    session = CodexSessionRead(
        run_id="run-1",
        workspace_id="ws-1",
        repo_path="/tmp/ws-1/repo",
        command=["codex", "exec", "--json"],
        status="completed",
        exit_code=0,
        summary_text="done",
        input_tokens=987,
        output_tokens=65,
        started_at="2026-03-08T10:06:00Z",
        finished_at="2026-03-08T10:08:00Z",
        last_output_offset=3,
    )
    service = RunService(
        run_repository=SimpleNamespace(),
        team_repository=SimpleNamespace(),
        export_service=SimpleNamespace(),
        workspace_proxy_service=SimpleNamespace(),
        codex_proxy_service=SimpleNamespace(get_session=lambda run_id: session),
        github_proxy_service=SimpleNamespace(),
        readiness_service=SimpleNamespace(),
    )
    service._sync_run_with_codex_session = lambda current_run: current_run

    enriched = service._enrich_run_for_read(run)

    assert enriched.input_tokens == 987
    assert enriched.output_tokens == 65


def test_run_read_schema_includes_usage_fields() -> None:
    """RunRead should serialize token usage from enriched run objects."""
    payload = RunRead.model_validate(
        SimpleNamespace(
            id="4b8efb16-f6f0-4ac1-bfea-42b3d3df6168",
            team_id=None,
            team_slug="delivery-team",
            team_title="Delivery Team",
            runtime_target="codex",
            repo_owner="stemirkhan",
            repo_name="team-agent-platform",
            repo_full_name="stemirkhan/team-agent-platform",
            base_branch="main",
            working_branch="tap/team-agent-platform/demo-branch",
            issue_number=None,
            issue_title=None,
            issue_url=None,
            title="Expose usage fallback",
            summary=None,
            task_text="Run codex and expose usage fallback.",
            runtime_config_json=None,
            workspace_id="ws-1",
            workspace_path="/tmp/ws-1",
            repo_path="/tmp/ws-1/repo",
            codex_session_id="session-1",
            transport_kind="pty",
            transport_ref="12345",
            resume_attempt_count=0,
            interrupted_at=None,
            input_tokens=987,
            output_tokens=65,
            status="completed",
            error_message=None,
            pr_url=None,
            started_at=None,
            finished_at=None,
            created_at="2026-03-08T10:00:00Z",
            updated_at="2026-03-08T10:10:00Z",
            run_report=None,
        )
    )

    assert payload.input_tokens == 987
    assert payload.output_tokens == 65
