# Architecture Overview

This document gives a high-level view of the platform architecture without diving into internal implementation details.

```mermaid
flowchart LR
    U[User in Browser]

    subgraph CP[Control Plane]
        W[Next.js Frontend]
        B[FastAPI Backend API]
        DB[(PostgreSQL)]
        R[(Redis)]
    end

    subgraph HE[Host Execution Layer]
        HX[Host Executor]
        PTY[PTY / tmux Sessions]
        GT[git CLI]
        GH[gh CLI]
        CX[codex CLI]
        WS[Local Workspace]
    end

    GHUB[GitHub]

    U --> W
    W --> B
    B --> DB
    B --> R
    B --> HX

    HX --> PTY
    HX --> GT
    HX --> GH
    HX --> CX
    HX --> WS

    GT --> GHUB
    GH --> GHUB
    CX --> WS

    B -->|run status, events, terminal bridge| W
    HX -->|diagnostics, session state, terminal output| B
```

In short:

- `Frontend` and `Backend` form the control plane.
- `Host Executor` runs in the host user context and has access to local `git`, `gh`, and `codex`.
- `Backend` orchestrates the run lifecycle, persists state in `PostgreSQL`, and serves status, history, and terminal data to the UI.
- `Host Executor` prepares workspaces, starts Codex sessions, and performs git/GitHub operations.
- GitHub remains the external source for repositories, issues, and draft PRs.

## Run Lifecycle

The diagram below shows the simplified lifecycle of a single `run`.

```mermaid
flowchart TD
    A[User starts Run in UI]
    B[Backend creates Run record]
    C[Backend asks Host Executor to prepare workspace]
    D[Clone repo and create working branch]
    E[Materialize .codex and TASK.md]
    F[Start codex session]
    G[Stream terminal and update run events]
    H[Run repo checks]
    I[Create commit]
    J[Push working branch]
    K[Create draft PR via gh]
    L[Run completed]

    X[Run interrupted or failed]
    Y[Resume or auto-recovery path]

    A --> B --> C --> D --> E --> F --> G --> H --> I --> J --> K --> L
    F --> X
    G --> X
    H --> X
    X --> Y --> F
```

In short:

- a run is initiated from the UI, but orchestrated by the backend;
- the host executor prepares the workspace and starts `codex`;
- terminal output and run events flow back through the backend and into the UI;
- on success, the flow ends with commit, push, and draft PR creation;
- on failure or interruption, the platform may use resume or auto-recovery when session state is still available.
