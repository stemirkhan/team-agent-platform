"""Shared payload schemas for agent markdown assets."""

from pydantic import BaseModel, Field


class AgentSkillPayload(BaseModel):
    """Structured agent skill stored inside manifest_json."""

    slug: str = Field(min_length=2, max_length=64)
    content: str = Field(min_length=1)
    description: str | None = Field(default=None, max_length=300)


class AgentMarkdownFilePayload(BaseModel):
    """Structured markdown file stored inside manifest_json."""

    path: str = Field(min_length=1, max_length=240)
    content: str = Field(min_length=1)
