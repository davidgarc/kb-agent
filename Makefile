API_PORT ?= 8000
CHAINLIT_PORT ?= 8001
API_BASE_URL ?= http://localhost:$(API_PORT)
RUN_DIR := .run
API_PID := $(RUN_DIR)/api.pid
CHAINLIT_PID := $(RUN_DIR)/chainlit.pid
API_LOG := $(RUN_DIR)/api.log
CHAINLIT_LOG := $(RUN_DIR)/chainlit.log

.PHONY: help start reset restart shutdown status logs ingest start-neo4j start-api start-ui wait-api stop-api stop-ui test

help:
	@printf "KB Agent local helpers\n\n"
	@printf "  make start       Start Neo4j, FastAPI, Chainlit, then ingest seed data\n"
	@printf "  make reset       Recreate Neo4j storage, restart services, then ingest seed data\n"
	@printf "  make restart     Restart services without deleting Neo4j storage\n"
	@printf "  make shutdown    Stop FastAPI, Chainlit, and Docker Compose services\n"
	@printf "  make status      Show service status and configured local URLs\n"
	@printf "  make logs        Tail API and Chainlit logs\n"
	@printf "  make ingest      Run POST /ingest/all against FastAPI\n"
	@printf "  make test        Run focused pytest suite\n"

start: start-neo4j start-api start-ui wait-api ingest status

restart: shutdown start

reset: stop-ui stop-api
	docker compose down -v
	$(MAKE) start

shutdown: stop-ui stop-api
	docker compose down

status:
	@printf "FastAPI:  %s\n" "$(API_BASE_URL)"
	@printf "Chainlit: http://localhost:%s\n" "$(CHAINLIT_PORT)"
	@printf "Neo4j:    http://localhost:7474\n"
	@docker compose ps neo4j || true
	@if [ -f "$(API_PID)" ] && kill -0 "$$(cat "$(API_PID)")" 2>/dev/null; then printf "API pid:  %s\n" "$$(cat "$(API_PID)")"; else printf "API pid:  not running\n"; fi
	@if [ -f "$(CHAINLIT_PID)" ] && kill -0 "$$(cat "$(CHAINLIT_PID)")" 2>/dev/null; then printf "UI pid:   %s\n" "$$(cat "$(CHAINLIT_PID)")"; else printf "UI pid:   not running\n"; fi

logs:
	@mkdir -p "$(RUN_DIR)"
	tail -f "$(API_LOG)" "$(CHAINLIT_LOG)"

ingest:
	curl -fsS -X POST "$(API_BASE_URL)/ingest/all"
	@printf "\n"

start-neo4j:
	docker compose up -d neo4j

start-api:
	@mkdir -p "$(RUN_DIR)"
	@if [ -f "$(API_PID)" ] && kill -0 "$$(cat "$(API_PID)")" 2>/dev/null; then \
		printf "FastAPI already running with pid %s\n" "$$(cat "$(API_PID)")"; \
	else \
		printf "Starting FastAPI on port %s\n" "$(API_PORT)"; \
		API_BASE_URL="$(API_BASE_URL)" nohup uv run uvicorn kb_agent.api.main:app --host 127.0.0.1 --port "$(API_PORT)" >"$(API_LOG)" 2>&1 & echo $$! >"$(API_PID)"; \
	fi

start-ui:
	@mkdir -p "$(RUN_DIR)"
	@if [ -f "$(CHAINLIT_PID)" ] && kill -0 "$$(cat "$(CHAINLIT_PID)")" 2>/dev/null; then \
		printf "Chainlit already running with pid %s\n" "$$(cat "$(CHAINLIT_PID)")"; \
	else \
		printf "Starting Chainlit on port %s\n" "$(CHAINLIT_PORT)"; \
		API_BASE_URL="$(API_BASE_URL)" nohup uv run chainlit run src/kb_agent/chainlit_app/app.py --host 127.0.0.1 --port "$(CHAINLIT_PORT)" >"$(CHAINLIT_LOG)" 2>&1 & echo $$! >"$(CHAINLIT_PID)"; \
	fi

wait-api:
	@printf "Waiting for FastAPI health"
	@for attempt in $$(seq 1 60); do \
		if curl -fsS "$(API_BASE_URL)/health" >/dev/null 2>&1; then \
			printf "\nFastAPI is healthy\n"; \
			exit 0; \
		fi; \
		printf "."; \
		sleep 1; \
	done; \
	printf "\nFastAPI did not become healthy. See $(API_LOG)\n"; \
	exit 1

stop-api:
	@if [ -f "$(API_PID)" ]; then \
		if kill -0 "$$(cat "$(API_PID)")" 2>/dev/null; then \
			printf "Stopping FastAPI pid %s\n" "$$(cat "$(API_PID)")"; \
			kill "$$(cat "$(API_PID)")"; \
		fi; \
		rm -f "$(API_PID)"; \
	fi

stop-ui:
	@if [ -f "$(CHAINLIT_PID)" ]; then \
		if kill -0 "$$(cat "$(CHAINLIT_PID)")" 2>/dev/null; then \
			printf "Stopping Chainlit pid %s\n" "$$(cat "$(CHAINLIT_PID)")"; \
			kill "$$(cat "$(CHAINLIT_PID)")"; \
		fi; \
		rm -f "$(CHAINLIT_PID)"; \
	fi

test:
	uv run --extra test pytest
