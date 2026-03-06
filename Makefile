COMPOSE_FILE := infra/compose/docker-compose.yml
ENV_FILE := .env

.PHONY: ensure-env up down logs ps compose-config backend-lint backend-test web-lint

ensure-env:
	@test -f $(ENV_FILE) || cp .env.example $(ENV_FILE)

up: ensure-env
	docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) up --build -d

down:
	docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) down

logs:
	docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) logs -f

ps:
	docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) ps

compose-config: ensure-env
	docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) config

backend-lint:
	cd apps/backend && python3 -m ruff check app tests

backend-test:
	cd apps/backend && python3 -m pytest

web-lint:
	cd apps/web && npm run lint
