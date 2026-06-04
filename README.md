# App Troubleshooting Knowledge Agent POC

Local POC for a chat-based troubleshooting agent scoped by application ID. It combines ServiceNow-style incidents, Markdown architecture/runbook docs, JSON infrastructure manifests, Neo4j graph traversal, Neo4j vector-style document retrieval, FastAPI APIs, LangChain tool wrappers, OpenRouter LLM synthesis, and a thin Chainlit demo UI.

## Architecture

- Chainlit is only the desktop chat shell.
- FastAPI owns ingestion, graph access, deterministic retrieval tools, and agent orchestration.
- Neo4j stores applications, components, dependencies, incidents, manifests, resources, doc chunks, provenance, constraints, full-text indexes, and a vector index.
- OpenRouter is used for final answer synthesis when `OPENROUTER_API_KEY` is available.
- Deterministic mock mode keeps the local showcase runnable without Neo4j or LLM access.

## Local Setup

```bash
cp .env.example .env
```

Set your OpenRouter key in `.env` or your shell:

```bash
export OPENROUTER_API_KEY=...
export KB_AGENT_USE_OPENROUTER=true
export OPENROUTER_MODEL=openai/gpt-4.1-mini
```

Install dependencies:

```bash
uv sync --extra test
```

Start the full local environment:

```bash
make start
```

This starts Neo4j, FastAPI on `http://localhost:8000`, Chainlit on `http://localhost:8001`, waits for FastAPI health, and runs `/ingest/all`.

Restart or shut down the local environment:

```bash
make reset
make shutdown
```

`make reset` deletes the local Neo4j Docker volume, starts the services again, and re-ingests the seed data. Use `make restart` if you only want to restart services without deleting graph storage.

You can also run each command manually. Start Neo4j:

```bash
docker compose up -d neo4j
```

Start FastAPI:

```bash
uv run uvicorn kb_agent.api.main:app --reload
```

Ingest seed data:

```bash
curl -X POST http://localhost:8000/ingest/all
```

Start Chainlit in a second terminal:

```bash
uv run chainlit run src/kb_agent/chainlit_app/app.py
```

Open Chainlit at the URL it prints, usually `http://localhost:8000` or `http://localhost:8001` depending on port availability. If FastAPI already uses `8000`, start Chainlit on another port:

```bash
uv run chainlit run src/kb_agent/chainlit_app/app.py --port 8001
```

## Useful API Commands

```bash
curl http://localhost:8000/health
curl http://localhost:8000/apps
curl http://localhost:8000/apps/APP001
curl http://localhost:8000/apps/APP001/graph
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"demo","app_id":"APP001","message":"What are the most likely causes of APP001 checkout latency?"}'
```

## Demo Data

The raw seed data is under `data/raw`:

- `incidents/servicenow_incidents.csv`
- `docs/APP001/architecture.md`
- `docs/APP001/runbook.md`
- `docs/APP002/architecture.md`
- `manifests/APP001/prod.json`
- `manifests/APP002/prod.json`

APP001 is Customer Checkout. APP002 is Inventory Fulfillment. APP001 depends on APP002 inventory-api.

Intentional inconsistency:

- APP001 architecture/runbook docs say the service uses `orders-db-primary` and queue `checkout-payment-events`.
- APP001 prod manifest points `ORDERS_DB_HOST` to `orders-db-replica` and configures `checkout-payment-events-v1`.
- Recent APP001 incidents mention connection failures, stale queue consumer errors, and backlog.

Ask:

```text
Do the architecture docs and deployed manifest disagree?
```

## Deterministic Fallback Mode

If Neo4j is not reachable, FastAPI automatically uses an in-memory repository. To force this mode:

```bash
export KB_AGENT_GRAPH_MODE=memory
uv run uvicorn kb_agent.api.main:app --reload
curl -X POST http://localhost:8000/ingest/all
```

If OpenRouter is unavailable, the agent still returns a deterministic structured answer from gathered evidence. The LLM only rewrites the already-built answer and summary.

## Tests

```bash
make test
```

The focused tests cover:

- idempotent ingestion,
- Markdown chunk provenance and embeddings,
- graph repository profile/search behavior,
- app-scoped tool results,
- discovery of the APP001 docs-versus-manifest inconsistency.

## Executive Demo Flow

1. Show raw incident CSV, Markdown docs, and JSON manifests.
2. Run `curl -X POST http://localhost:8000/ingest/all`.
3. Open Neo4j Browser at `http://localhost:7474` and log in with `neo4j/password`.
4. Run a graph query such as:

```cypher
MATCH (a:Application {app_id: "APP001"})-[r]->(n)
RETURN a, r, n
```

5. Open Chainlit and ask: `For APP001, what are the most likely causes of checkout latency?`
6. Ask: `Do the architecture docs and manifest agree?`
7. Ask: `Give me an executive incident briefing for APP001.`

## Non-Goals

This POC does not implement production auth, live ServiceNow ingestion, real-time event streams, arbitrary Cypher generation, automated remediation, or enterprise deployment hardening.
