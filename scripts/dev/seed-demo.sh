#!/usr/bin/env sh
set -eu

API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000/api/v1}"
DEMO_EMAIL="${DEMO_EMAIL:-demo@team-agent-platform.local}"
DEMO_PASSWORD="${DEMO_PASSWORD:-demo-password-123}"
DEMO_DISPLAY_NAME="${DEMO_DISPLAY_NAME:-Platform Demo}"

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

seed_agent() {
  slug="$1"
  title="$2"
  short_description="$3"
  full_description="$4"
  category="$5"
  codex_instructions="$6"
  token="$7"

  create_payload="$(cat <<EOF
{"slug":"$slug","title":"$title","short_description":"$short_description","full_description":"$full_description","category":"$category"}
EOF
)"
  create_result="$(request POST /agents "$create_payload" "$token")"
  create_status="$(printf '%s\n' "$create_result" | sed -n '1p')"
  create_body="$(printf '%s\n' "$create_result" | sed '1d')"
  if [ "$create_status" != "201" ] && [ "$create_status" != "409" ]; then
    printf 'Agent create failed for %s.\n%s\n' "$slug" "$create_body" >&2
    exit 1
  fi

  profile_payload="$(cat <<EOF
{"manifest_json":{"codex":{"description":"$title","model_reasoning_effort":"medium","sandbox_mode":"workspace-write","developer_instructions":"$codex_instructions"}},"compatibility_matrix":{"codex":true},"export_targets":["codex"],"install_instructions":"Import this agent into your local runtime configuration."}
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
}

token="$(authenticate)"

seed_agent \
  "fastapi-reviewer" \
  "FastAPI Reviewer" \
  "Inspects FastAPI services, routers, and release readiness." \
  "Looks for service boundaries, schema drift, and API contract issues in FastAPI backends." \
  "backend" \
  "Audit FastAPI routers, schemas, services, and exports. Flag correctness, missing validation, and unsafe changes." \
  "$token"

seed_agent \
  "nextjs-ui-builder" \
  "Next.js UI Builder" \
  "Designs and refines Next.js interfaces for production MVP flows." \
  "Improves page structure, interaction details, and component polish for Next.js App Router applications." \
  "frontend" \
  "Refine Next.js UI structure, improve hierarchy, and keep Tailwind implementation maintainable." \
  "$token"

seed_agent \
  "runtime-export-auditor" \
  "Runtime Export Auditor" \
  "Checks export compatibility for Codex." \
  "Validates Codex manifests, config fields, and packaging expectations for supported exports." \
  "tooling" \
  "Validate export manifests for Codex. Focus on config completeness and portability." \
  "$token"

printf 'Seeded demo user: %s\n' "$DEMO_EMAIL"
printf 'Seeded published agents:\n'
printf ' - fastapi-reviewer\n'
printf ' - nextjs-ui-builder\n'
printf ' - runtime-export-auditor\n'
