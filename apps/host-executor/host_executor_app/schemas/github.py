"""Schemas for GitHub tracker and repository data."""

from pydantic import BaseModel, Field


class GitHubRepoRead(BaseModel):
    """Normalized GitHub repository metadata."""

    owner: str
    name: str
    full_name: str
    description: str | None = None
    url: str
    ssh_url: str | None = None
    is_private: bool
    visibility: str | None = None
    default_branch: str | None = None
    has_issues_enabled: bool = True
    viewer_permission: str | None = None
    updated_at: str | None = None
    pushed_at: str | None = None


class GitHubRepoListResponse(BaseModel):
    """Paginated repository list."""

    items: list[GitHubRepoRead] = Field(default_factory=list)
    total: int
    limit: int


class GitHubIssueRead(BaseModel):
    """Normalized GitHub issue payload."""

    number: int
    title: str
    body: str | None = None
    state: str
    url: str
    author_login: str | None = None
    labels: list[str] = Field(default_factory=list)
    comments_count: int = 0
    created_at: str | None = None
    updated_at: str | None = None


class GitHubIssueCommentRead(BaseModel):
    """Normalized GitHub issue comment payload."""

    id: str | None = None
    author_login: str | None = None
    body: str
    url: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class GitHubIssueDetailRead(GitHubIssueRead):
    """Full issue payload with comments for detail views and mutations."""

    comments: list[GitHubIssueCommentRead] = Field(default_factory=list)


class GitHubIssueCommentCreate(BaseModel):
    """Payload for adding a comment to an issue."""

    body: str = Field(min_length=1, max_length=65535)


class GitHubIssueLabelsUpdate(BaseModel):
    """Payload for adding labels to an issue."""

    labels: list[str] = Field(min_length=1, max_length=20)


class GitHubIssueListResponse(BaseModel):
    """Paginated issue list."""

    items: list[GitHubIssueRead] = Field(default_factory=list)
    total: int
    limit: int
    state: str


class GitHubPullRead(BaseModel):
    """Normalized GitHub pull request payload."""

    number: int
    title: str
    body: str | None = None
    state: str
    url: str
    author_login: str | None = None
    labels: list[str] = Field(default_factory=list)
    comments_count: int = 0
    is_draft: bool = False
    base_ref_name: str | None = None
    head_ref_name: str | None = None
    merge_state_status: str | None = None
    mergeable: str | None = None
    review_decision: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class GitHubPullListResponse(BaseModel):
    """Paginated pull request list."""

    items: list[GitHubPullRead] = Field(default_factory=list)
    total: int
    limit: int
    state: str


class GitHubPullCheckRead(BaseModel):
    """Normalized pull request check payload."""

    name: str
    state: str
    bucket: str | None = None
    workflow: str | None = None
    description: str | None = None
    event: str | None = None
    link: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


class GitHubPullChecksSummary(BaseModel):
    """Bucket-level summary for pull request checks."""

    pass_count: int = 0
    fail_count: int = 0
    pending_count: int = 0
    skipping_count: int = 0
    cancel_count: int = 0


class GitHubPullChecksResponse(BaseModel):
    """Normalized pull request checks response."""

    items: list[GitHubPullCheckRead] = Field(default_factory=list)
    total: int
    summary: GitHubPullChecksSummary = Field(default_factory=GitHubPullChecksSummary)
