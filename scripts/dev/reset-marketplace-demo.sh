#!/usr/bin/env sh
set -eu

API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000/api/v1}"
COMPOSE_FILE="${COMPOSE_FILE:-infra/compose/docker-compose.yml}"
POSTGRES_DB="${POSTGRES_DB:-agent_marketplace}"
POSTGRES_USER="${POSTGRES_USER:-agent_marketplace}"
DEMO_EMAIL="${DEMO_EMAIL:-demo@team-agent-platform.local}"
DEMO_PASSWORD="${DEMO_PASSWORD:-demo-password-123}"
DEMO_DISPLAY_NAME="${DEMO_DISPLAY_NAME:-Marketplace Demo}"

if [ -z "${XDG_DATA_HOME:-}" ] || echo "${XDG_DATA_HOME}" | grep -q '/snap/code/'; then
  export XDG_DATA_HOME="${HOME}/.local/share"
fi

parse_json_field() {
  field_name="$1"
  python3 -c "import json,sys; print(json.load(sys.stdin)['$field_name'])"
}

request() {
  method="$1"
  path="$2"
  payload="$3"
  token="${4:-}"

  response_file="$(mktemp)"
  if [ -n "$token" ]; then
    status_code="$(
      curl -sS -o "$response_file" -w '%{http_code}' \
        -X "$method" "$API_BASE_URL$path" \
        -H 'Content-Type: application/json' \
        -H "Authorization: Bearer $token" \
        --data "$payload"
    )"
  else
    status_code="$(
      curl -sS -o "$response_file" -w '%{http_code}' \
        -X "$method" "$API_BASE_URL$path" \
        -H 'Content-Type: application/json' \
        --data "$payload"
    )"
  fi

  printf '%s\n' "$status_code"
  cat "$response_file"
  rm -f "$response_file"
}

psql_exec() {
  sql="$1"
  podman-compose -f "$COMPOSE_FILE" exec -T postgres \
    psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "$sql"
}

authenticate() {
  register_payload="$(cat <<EOF
{"email":"$DEMO_EMAIL","password":"$DEMO_PASSWORD","display_name":"$DEMO_DISPLAY_NAME"}
EOF
)"

  register_result="$(request POST /auth/register "$register_payload")"
  register_status="$(printf '%s\n' "$register_result" | sed -n '1p')"
  register_body="$(printf '%s\n' "$register_result" | sed '1d')"

  if [ "$register_status" = "201" ]; then
    printf '%s' "$register_body" | parse_json_field access_token
    return 0
  fi

  login_payload="$(cat <<EOF
{"email":"$DEMO_EMAIL","password":"$DEMO_PASSWORD"}
EOF
)"
  login_result="$(request POST /auth/login "$login_payload")"
  login_status="$(printf '%s\n' "$login_result" | sed -n '1p')"
  login_body="$(printf '%s\n' "$login_result" | sed '1d')"

  if [ "$login_status" != "200" ]; then
    printf 'Authentication failed.\n%s\n' "$login_body" >&2
    exit 1
  fi

  printf '%s' "$login_body" | parse_json_field access_token
}

reset_marketplace_data() {
  printf 'Resetting agents, teams, internal profiles, and exports...\n'
  psql_exec "TRUNCATE TABLE exports, team_items, teams, agent_versions, agents RESTART IDENTITY CASCADE;"
}

seed_agent() {
  slug="$1"
  title="$2"
  short_description="$3"
  full_description="$4"
  category="$5"
  general_instructions="$6"
  codex_instructions="$7"
  token="${8}"

  tools_required='[]'
  permissions_required='[]'
  tags='[]'
  skills='[]'
  markdown_files='[]'

  case "$slug" in
    "backend-platform-engineer")
      tools_required='["python","fastapi","sqlalchemy","alembic","pytest","postgresql"]'
      permissions_required='["read_repository","edit_application_code","run_tests","inspect_database_schema","review_migrations"]'
      tags='["backend","fastapi","python","sqlalchemy","architecture","api"]'
      skills='[{"slug":"backend-release-audit","description":"Checklist for backend changes before release.","content":"# Backend release audit\n\n1. Review API contracts and schema changes.\n2. Inspect migrations and rollback path.\n3. Run backend checks and summarize release risk."}]'
      markdown_files='[{"path":"AGENTS.md","content":"# Backend Platform Engineer\n\nUse this agent for FastAPI architecture, schema changes, migrations, and production-safe backend delivery."}]'
      ;;
    "frontend-product-engineer")
      tools_required='["nodejs","nextjs","typescript","tailwindcss","npm"]'
      permissions_required='["read_repository","edit_application_code","run_frontend_checks","review_ui_states"]'
      tags='["frontend","nextjs","typescript","tailwind","ux","product-ui"]'
      skills='[{"slug":"frontend-ux-review","description":"Checklist for production UI refinement.","content":"# Frontend UX review\n\n1. Check page hierarchy and CTA clarity.\n2. Verify empty, loading, and error states.\n3. Confirm responsive layout and visual consistency."}]'
      markdown_files='[{"path":"docs/ui-guidelines.md","content":"# UI guidelines\n\nKeep hierarchy explicit, states visible, and Tailwind implementation maintainable."}]'
      ;;
    "delivery-orchestrator")
      tools_required='["planning","repository-search","issue-triage","release-coordination"]'
      permissions_required='["read_repository","coordinate_multi_agent_work","propose_execution_plan","review_cross_functional_scope"]'
      tags='["orchestration","delivery","planning","coordination","fullstack"]'
      skills='[{"slug":"delivery-checkpoint","description":"Cross-functional delivery checkpoint.","content":"# Delivery checkpoint\n\n1. Reconfirm scope and owners.\n2. Check backend and frontend dependency order.\n3. Verify integrated release readiness."}]'
      markdown_files='[{"path":"docs/delivery-playbook.md","content":"# Delivery playbook\n\nBreak work into backend and frontend tracks, then validate the integrated result before sign-off."}]'
      ;;
  esac

  printf 'Creating agent %s...\n' "$slug" >&2

  create_payload="$(cat <<EOF
{"slug":"$slug","title":"$title","short_description":"$short_description","full_description":"$full_description","category":"$category"}
EOF
)"
  create_result="$(request POST /agents "$create_payload" "$token")"
  create_status="$(printf '%s\n' "$create_result" | sed -n '1p')"
  create_body="$(printf '%s\n' "$create_result" | sed '1d')"
  if [ "$create_status" != "201" ]; then
    printf 'Agent create failed for %s.\n%s\n' "$slug" "$create_body" >&2
    exit 1
  fi

  profile_payload="$(cat <<EOF
{"manifest_json":{"description":"$full_description","instructions":"$general_instructions","tools_required":$tools_required,"permissions_required":$permissions_required,"tags":$tags,"codex":{"description":"$title","model_reasoning_effort":"medium","sandbox_mode":"workspace-write","developer_instructions":"$codex_instructions"}},"compatibility_matrix":{"codex":true,"claude_code":true},"export_targets":["codex","claude_code"],"install_instructions":"$general_instructions","skills":$skills,"markdown_files":$markdown_files}
EOF
)"
  profile_result="$(request PATCH "/agents/$slug" "$profile_payload" "$token")"
  profile_status="$(printf '%s\n' "$profile_result" | sed -n '1p')"
  profile_body="$(printf '%s\n' "$profile_result" | sed '1d')"
  if [ "$profile_status" != "200" ]; then
    printf 'Profile update failed for %s.\n%s\n' "$slug" "$profile_body" >&2
    exit 1
  fi

  publish_result="$(request POST "/agents/$slug/publish" '{}' "$token")"
  publish_status="$(printf '%s\n' "$publish_result" | sed -n '1p')"
  publish_body="$(printf '%s\n' "$publish_result" | sed '1d')"
  if [ "$publish_status" != "200" ]; then
    printf 'Publish failed for %s.\n%s\n' "$slug" "$publish_body" >&2
    exit 1
  fi

  printf '%s\n' "$slug"
}

seed_team() {
  slug="$1"
  title="$2"
  description="$3"
  orchestrator_slug="$4"
  backend_slug="$5"
  frontend_slug="$6"
  token="$7"

  printf 'Creating team %s...\n' "$slug" >&2

  create_payload="$(cat <<EOF
{"slug":"$slug","title":"$title","description":"$description"}
EOF
)"
  create_result="$(request POST /teams "$create_payload" "$token")"
  create_status="$(printf '%s\n' "$create_result" | sed -n '1p')"
  create_body="$(printf '%s\n' "$create_result" | sed '1d')"
  if [ "$create_status" != "201" ]; then
    printf 'Team create failed for %s.\n%s\n' "$slug" "$create_body" >&2
    exit 1
  fi

  orchestrator_item_payload="$(cat <<EOF
{"agent_slug":"$orchestrator_slug","role_name":"orchestrator","order_index":0,"is_required":true}
EOF
)"
  backend_item_payload="$(cat <<EOF
{"agent_slug":"$backend_slug","role_name":"backend-engineer","order_index":1,"is_required":true}
EOF
)"
  frontend_item_payload="$(cat <<EOF
{"agent_slug":"$frontend_slug","role_name":"frontend-engineer","order_index":2,"is_required":true}
EOF
)"

  for payload in "$orchestrator_item_payload" "$backend_item_payload" "$frontend_item_payload"; do
    item_result="$(request POST "/teams/$slug/items" "$payload" "$token")"
    item_status="$(printf '%s\n' "$item_result" | sed -n '1p')"
    item_body="$(printf '%s\n' "$item_result" | sed '1d')"
    if [ "$item_status" != "200" ]; then
      printf 'Team item create failed for %s.\n%s\n' "$slug" "$item_body" >&2
      exit 1
    fi
  done

  publish_result="$(request POST "/teams/$slug/publish" '{}' "$token")"
  publish_status="$(printf '%s\n' "$publish_result" | sed -n '1p')"
  publish_body="$(printf '%s\n' "$publish_result" | sed '1d')"
  if [ "$publish_status" != "200" ]; then
    printf 'Team publish failed for %s.\n%s\n' "$slug" "$publish_body" >&2
    exit 1
  fi
}

reset_marketplace_data
token="$(authenticate)"

backend_slug="$(
  seed_agent \
    "backend-platform-engineer" \
    "Backend Platform Engineer" \
    "Owns FastAPI backend architecture, data contracts, migrations, and release-safe API implementation for production delivery." \
    "Acts as the backend owner for a real product codebase. This agent is responsible for understanding the existing backend architecture, mapping domain boundaries, reviewing routers, schemas, services, repositories, SQLAlchemy models, migrations, and integration points, then implementing or refining backend changes without breaking existing contracts. It should prefer explicit validation, deterministic data flows, backward-compatible API changes, clean transactional boundaries, and maintainable code structure. It must watch for schema drift, weak typing, unsafe defaults, missing edge-case handling, broken ownership rules, incomplete migrations, and coupling between delivery logic and transport logic. Expected outputs include implementation plans, API contract decisions, concrete backend code changes, migration strategy, validation notes, and a short risk summary before major modifications." \
    "backend" \
    "Start by mapping the backend structure, data models, migrations, and API entrypoints. Work from repository evidence instead of assumptions. Treat API contracts and database consistency as critical constraints. When implementing changes, prefer simple service boundaries, explicit validation, safe defaults, reversible migrations, and testable behavior. Flag breaking changes, migration risk, inconsistent naming, hidden coupling, and any area where production reliability may regress." \
    "You are the backend implementation owner. Review FastAPI routers, Pydantic schemas, service layer, repositories, SQLAlchemy models, Alembic migrations, auth boundaries, and export logic. Keep the system stable, explicit, and production-minded. Before changing code, identify contract risks and data integrity constraints. When writing code, avoid hidden magic, avoid weak validation, preserve backward compatibility where possible, and explain migration or rollout implications." \
    "$token"
)"

frontend_slug="$(
  seed_agent \
    "frontend-product-engineer" \
    "Frontend Product Engineer" \
    "Owns Next.js product UI, page flows, interaction states, and maintainable Tailwind implementation for production MVP delivery." \
    "Acts as the frontend owner for a real product interface. This agent is responsible for understanding the current page structure, layout patterns, navigation, forms, empty states, loading states, and client-side interactions, then improving or implementing UI without introducing visual inconsistency or unnecessary architectural weight. It should preserve product clarity, responsive behavior, accessibility basics, and maintainable component boundaries. It must avoid generic boilerplate layouts, avoid overcomplicated client state, and watch for broken hierarchy, weak affordances, missing states, unclear CTA structure, and visual drift between pages. Expected outputs include UI implementation decisions, component-level changes, layout refinements, interaction improvements, and a short usability-risk note when relevant." \
    "frontend" \
    "Start by mapping the product flow, layout structure, key forms, navigation, and current interaction states. Improve hierarchy, readability, spacing, CTA clarity, and responsive behavior before adding complexity. Keep Tailwind styling intentional and reusable, preserve consistency across pages, and make sure empty, loading, error, and success states are explicit. Avoid unnecessary state layers and avoid generic design decisions that dilute product clarity." \
    "You are the frontend implementation owner. Review Next.js App Router pages, client components, forms, navigation, state boundaries, theming, and Tailwind usage. Improve UX clarity, hierarchy, and interaction quality while keeping implementation direct and maintainable. Prefer deliberate product UI, explicit states, and cohesive component patterns over generic layouts and unnecessary abstractions." \
    "$token"
)"

orchestrator_slug="$(
  seed_agent \
    "delivery-orchestrator" \
    "Delivery Orchestrator" \
    "Coordinates backend and frontend specialists, breaks delivery into stages, and keeps scope, dependencies, and release quality aligned." \
    "Acts as the orchestrator for cross-functional delivery in a real product repository. This agent is responsible for understanding the request, decomposing work into backend and frontend tracks, identifying dependencies and sequencing, assigning clear ownership, and making sure the final delivery remains coherent, minimal, and release-ready. It should preserve scope discipline, protect the critical path, and avoid parallel changes that create avoidable merge or integration risk. It must watch for hidden dependency chains, unclear ownership, missing validation, incomplete end-to-end flow, and premature expansion of scope. Expected outputs include an execution plan, delegation outline, integration checkpoints, summary of open risks, and a final validation view of whether the combined result is shippable." \
    "orchestration" \
    "Start by clarifying the request, then break the work into concrete backend and frontend tracks with explicit ownership and sequencing. Keep the plan minimal and execution-oriented. Surface blockers early, reduce scope when needed, and make sure the final outcome is integrated end to end rather than locally correct but globally inconsistent. Before sign-off, check that backend, frontend, and export behavior still align with the requested outcome." \
    "You are the delivery orchestrator. Read the request, identify constraints, split work between backend and frontend specialists, keep ownership explicit, and protect the critical delivery path. Avoid scope creep, avoid duplicate work, and ensure the final result is coherent across API, UI, and export flows. Your value is coordination, sequencing, integration review, and release readiness." \
    "$token"
)"

seed_team \
  "fullstack-delivery-squad" \
  "Fullstack Delivery Squad" \
  "Cross-functional product delivery team that uses a delivery orchestrator to coordinate backend and frontend specialists, then ships product features end to end with clear sequencing, explicit ownership, and release-minded validation." \
  "$orchestrator_slug" \
  "$backend_slug" \
  "$frontend_slug" \
  "$token"

printf '\nSeed complete.\n'
printf 'Published agents:\n'
printf ' - backend-platform-engineer\n'
printf ' - frontend-product-engineer\n'
printf ' - delivery-orchestrator\n'
printf 'Published team:\n'
printf ' - fullstack-delivery-squad\n'
printf 'Demo user:\n'
printf ' - email: %s\n' "$DEMO_EMAIL"
printf ' - password: %s\n' "$DEMO_PASSWORD"
