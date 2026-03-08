"""Public download endpoints for export artifacts."""

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.api.deps import get_export_service
from app.models.export_job import ExportEntityType, RuntimeTarget
from app.schemas.export import ClaudeExportOptions, CodexExportOptions, OpenCodeExportOptions
from app.services.export_service import ExportService

router = APIRouter(prefix="/downloads", tags=["downloads"])


@router.get("/agent/{slug}/codex.toml")
def download_agent_codex_export_artifact(
    slug: str,
    codex_options: CodexExportOptions = Depends(),
    service: ExportService = Depends(get_export_service),
) -> Response:
    """Build and return TOML artifact for a published agent."""
    filename, content, media_type = service.build_download_artifact(
        entity_type=ExportEntityType.AGENT,
        slug=slug,
        runtime_target=RuntimeTarget.CODEX.value,
        codex_options=codex_options,
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content, media_type=media_type, headers=headers)


@router.get("/agent/{slug}/claude_code.md")
def download_agent_claude_export_artifact(
    slug: str,
    claude_options: ClaudeExportOptions = Depends(),
    service: ExportService = Depends(get_export_service),
) -> Response:
    """Build and return Markdown artifact for a published agent."""
    filename, content, media_type = service.build_download_artifact(
        entity_type=ExportEntityType.AGENT,
        slug=slug,
        runtime_target=RuntimeTarget.CLAUDE_CODE.value,
        claude_options=claude_options,
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content, media_type=media_type, headers=headers)


@router.get("/agent/{slug}/codex.zip")
def download_agent_codex_export_bundle(
    slug: str,
    codex_options: CodexExportOptions = Depends(),
    service: ExportService = Depends(get_export_service),
) -> Response:
    """Build and return ZIP Codex bundle for a published agent."""
    filename, content, media_type = service.build_download_artifact(
        entity_type=ExportEntityType.AGENT,
        slug=slug,
        runtime_target=RuntimeTarget.CODEX.value,
        codex_options=codex_options,
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content, media_type=media_type, headers=headers)


@router.get("/team/{slug}/codex.zip")
def download_team_codex_export_artifact(
    slug: str,
    codex_options: CodexExportOptions = Depends(),
    service: ExportService = Depends(get_export_service),
) -> Response:
    """Build and return ZIP Codex bundle for a published team."""
    filename, content, media_type = service.build_download_artifact(
        entity_type=ExportEntityType.TEAM,
        slug=slug,
        runtime_target=RuntimeTarget.CODEX.value,
        codex_options=codex_options,
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content, media_type=media_type, headers=headers)


@router.get("/team/{slug}/claude_code.zip")
def download_team_claude_export_artifact(
    slug: str,
    claude_options: ClaudeExportOptions = Depends(),
    service: ExportService = Depends(get_export_service),
) -> Response:
    """Build and return ZIP Claude Code bundle for a published team."""
    filename, content, media_type = service.build_download_artifact(
        entity_type=ExportEntityType.TEAM,
        slug=slug,
        runtime_target=RuntimeTarget.CLAUDE_CODE.value,
        claude_options=claude_options,
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content, media_type=media_type, headers=headers)


@router.get("/agent/{slug}/opencode.md")
def download_agent_opencode_export_artifact(
    slug: str,
    opencode_options: OpenCodeExportOptions = Depends(),
    service: ExportService = Depends(get_export_service),
) -> Response:
    """Build and return Markdown artifact for a published OpenCode agent."""
    filename, content, media_type = service.build_download_artifact(
        entity_type=ExportEntityType.AGENT,
        slug=slug,
        runtime_target=RuntimeTarget.OPENCODE.value,
        opencode_options=opencode_options,
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content, media_type=media_type, headers=headers)


@router.get("/agent/{slug}/claude_code.zip")
def download_agent_claude_export_bundle(
    slug: str,
    claude_options: ClaudeExportOptions = Depends(),
    service: ExportService = Depends(get_export_service),
) -> Response:
    """Build and return ZIP Claude Code bundle for a published agent."""
    filename, content, media_type = service.build_download_artifact(
        entity_type=ExportEntityType.AGENT,
        slug=slug,
        runtime_target=RuntimeTarget.CLAUDE_CODE.value,
        claude_options=claude_options,
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content, media_type=media_type, headers=headers)


@router.get("/agent/{slug}/opencode.zip")
def download_agent_opencode_export_bundle(
    slug: str,
    opencode_options: OpenCodeExportOptions = Depends(),
    service: ExportService = Depends(get_export_service),
) -> Response:
    """Build and return ZIP OpenCode bundle for a published agent."""
    filename, content, media_type = service.build_download_artifact(
        entity_type=ExportEntityType.AGENT,
        slug=slug,
        runtime_target=RuntimeTarget.OPENCODE.value,
        opencode_options=opencode_options,
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content, media_type=media_type, headers=headers)


@router.get("/team/{slug}/opencode.zip")
def download_team_opencode_export_artifact(
    slug: str,
    opencode_options: OpenCodeExportOptions = Depends(),
    service: ExportService = Depends(get_export_service),
) -> Response:
    """Build and return ZIP OpenCode bundle for a published team."""
    filename, content, media_type = service.build_download_artifact(
        entity_type=ExportEntityType.TEAM,
        slug=slug,
        runtime_target=RuntimeTarget.OPENCODE.value,
        opencode_options=opencode_options,
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content, media_type=media_type, headers=headers)
