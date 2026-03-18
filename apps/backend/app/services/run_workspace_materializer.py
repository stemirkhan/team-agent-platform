"""Task markdown and SCM finalization materialization for one run."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException, status

from app.models.export_job import RuntimeTarget
from app.schemas.run import RunCreate
from app.schemas.workspace import WorkspaceFileWrite
from app.services.export_service import ExportService
from app.services.runtime_adapters import (
    BackendRuntimeAdapter,
    RuntimeAdapterError,
    RuntimeAdapterRegistry,
)


class RunWorkspaceMaterializer:
    """Build workspace scaffolding files for runtime-managed runs."""

    _FINALIZE_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "assets" / "finalize_run.py.tmpl"

    def __init__(
        self,
        *,
        export_service: ExportService,
        runtime_adapters: RuntimeAdapterRegistry,
    ) -> None:
        self.export_service = export_service
        self.runtime_adapters = runtime_adapters

    def build_workspace_files(
        self,
        *,
        run,
        runtime_target: str,
        team_slug: str,
        team_startup_prompt: str | None,
        payload: RunCreate,
        repo_full_name: str,
        base_branch: str,
        working_branch: str,
        issue_title: str | None,
        issue_number: int | None,
        issue_url: str | None,
        issue_body: str | None,
    ) -> list[WorkspaceFileWrite]:
        """Return text files that should be written into the prepared workspace."""
        adapter = self.get_runtime_adapter(runtime_target)
        commit_message = self.build_commit_message(run)
        pr_title = self.build_pr_title(run)
        pr_body = self.build_pr_body(run)
        task_markdown = self.build_task_markdown(
            payload=payload,
            team_startup_prompt=team_startup_prompt,
            repo_full_name=repo_full_name,
            base_branch=base_branch,
            working_branch=working_branch,
            issue_title=issue_title,
            issue_number=issue_number,
            issue_url=issue_url,
            issue_body=issue_body,
            commit_message=commit_message,
            pr_title=pr_title,
        )
        try:
            files = adapter.build_workspace_files(
                export_service=self.export_service,
                team_slug=team_slug,
                task_markdown=task_markdown,
                codex_options=payload.codex,
            )
        except RuntimeAdapterError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

        file_map = {item.path: item.content for item in files}
        file_map[".tap/finalize_run.py"] = self.render_finalize_script(
            repo_full_name=repo_full_name,
            base_branch=base_branch,
            working_branch=working_branch,
            commit_message=commit_message,
            pr_title=pr_title,
            pr_body=pr_body,
        )
        return [
            WorkspaceFileWrite(path=path, content=content)
            for path, content in sorted(file_map.items())
        ]

    def get_runtime_adapter(self, runtime_target: str) -> BackendRuntimeAdapter:
        """Return one registered runtime adapter or raise a normalized HTTP error."""
        adapter = self.runtime_adapters.get(runtime_target)
        if adapter is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Runtime '{runtime_target}' runs are not implemented yet.",
            )
        return adapter

    @classmethod
    def render_finalize_script(
        cls,
        *,
        repo_full_name: str,
        base_branch: str,
        working_branch: str,
        commit_message: str,
        pr_title: str,
        pr_body: str,
    ) -> str:
        """Render the runtime finalization helper from a versioned template asset."""
        replacements = {
            "__REPO_FULL_NAME__": json.dumps(repo_full_name),
            "__BASE_BRANCH__": json.dumps(base_branch),
            "__WORKING_BRANCH__": json.dumps(working_branch),
            "__COMMIT_MESSAGE__": json.dumps(commit_message),
            "__PR_TITLE__": json.dumps(pr_title),
            "__PR_BODY__": json.dumps(pr_body),
        }
        content = cls._load_finalize_template()
        for token, value in replacements.items():
            content = content.replace(token, value)
        return content.rstrip() + "\n"

    @classmethod
    @lru_cache(maxsize=1)
    def _load_finalize_template(cls) -> str:
        """Load the finalization script template from disk once per process."""
        return cls._FINALIZE_TEMPLATE_PATH.read_text(encoding="utf-8")

    @classmethod
    def build_task_markdown(
        cls,
        *,
        payload: RunCreate,
        team_startup_prompt: str | None,
        repo_full_name: str,
        base_branch: str,
        working_branch: str,
        issue_title: str | None,
        issue_number: int | None,
        issue_url: str | None,
        issue_body: str | None,
        commit_message: str,
        pr_title: str,
    ) -> str:
        """Render the task handoff file materialized into the repo workspace."""
        lines = [
            f"# {payload.title or issue_title or 'Execution Task'}",
        ]
        if team_startup_prompt and team_startup_prompt.strip():
            lines.extend(
                [
                    "",
                    "## Team Startup Prompt",
                    team_startup_prompt.strip(),
                ]
            )
        lines.extend(
            [
                "",
                "## Context",
                f"- Repository: `{repo_full_name}`",
                f"- Base branch: `{base_branch}`",
                f"- Working branch: `{working_branch}`",
                f"- Team: `{payload.team_slug}`",
            ]
        )
        lines.extend(
            [
                "",
                "## Required Outcome",
                "- Complete the requested repository changes.",
                (
                    "- Create the draft PR yourself from the prepared working branch "
                    "before ending the run."
                ),
                (
                    "- Treat the run as incomplete until the draft PR exists, unless cleanup "
                    "proves that no repository changes remain."
                ),
            ]
        )
        if payload.summary:
            lines.extend(["", "## Goal Summary", payload.summary.strip()])
        if issue_number is not None:
            lines.extend(
                [
                    "",
                    "## GitHub Issue",
                    f"- Number: `#{issue_number}`",
                ]
            )
            if issue_title:
                lines.append(f"- Title: {issue_title}")
            if issue_url:
                lines.append(f"- URL: {issue_url}")
            if issue_body:
                lines.extend(["", "### Issue Body", issue_body.strip()])
        if payload.task_text:
            lines.extend(["", "## Task Instructions", payload.task_text.strip()])
        lines.extend(
            [
                "",
                "## Constraints",
                "- Keep changes scoped to the requested task.",
                "- Prefer minimal, reviewable edits over broad rewrites.",
                "- Avoid modifying unrelated files.",
            ]
        )
        lines.extend(
            [
                "",
                "## SCM Finalization",
                (
                    "- After implementation and validation are complete, finalize the branch "
                    "yourself from the repo root."
                ),
                (
                    "- Run `python3 .tap/finalize_run.py` to remove runtime scaffolding, "
                    "commit the remaining repo changes, push the working branch, and open "
                    "the draft PR."
                ),
                "- Backend will not create the commit, push the branch, or open the PR for you.",
                (
                    "- If the script reports that no repository changes remain after cleanup, "
                    "do not create an empty commit or PR."
                ),
                "",
                "### Expected Git Metadata",
                f"- Commit message: `{commit_message}`",
                f"- Draft PR title: `{pr_title}`",
            ]
        )
        return "\n".join(lines).strip() + "\n"

    def build_commit_message(self, run) -> str:
        """Return a deterministic git commit message for one finalized run."""
        title = run.title.strip()
        runtime_slug = self.get_runtime_adapter(run.runtime_target).summary_label
        if run.issue_number is not None:
            return f"chore(run): address #{run.issue_number} {title[:140]}".strip()
        return f"chore(run): apply {runtime_slug} changes for {title[:160]}".strip()

    @staticmethod
    def build_pr_title(run) -> str:
        """Return a stable draft PR title for one run."""
        if run.issue_number is not None:
            return f"[tap] #{run.issue_number} {run.title}".strip()
        return f"[tap] {run.title}".strip()

    @staticmethod
    def build_pr_body(run) -> str:
        """Return a concise PR body describing the automated run context."""
        lines = [
            "## Team Agent Platform run",
            "",
            f"- Team: `{run.team_title}`",
            f"- Repository: `{run.repo_full_name}`",
            f"- Base branch: `{run.base_branch}`",
            f"- Working branch: `{run.working_branch or '-'}`",
        ]
        if run.issue_number is not None:
            lines.append(f"- Issue: #{run.issue_number}")
        if run.issue_url:
            lines.append(f"- Issue URL: {run.issue_url}")
        if run.summary:
            lines.extend(["", "## Summary", run.summary.strip()])
        if run.task_text:
            lines.extend(["", "## Task", run.task_text.strip()])
        lines.extend(
            [
                "",
                "## Notes",
                "- This draft PR was created by the local host-execution flow.",
                "- Review the diff and run project-specific checks before merging.",
            ]
        )
        body = "\n".join(lines).strip()
        return body[:19_500]
