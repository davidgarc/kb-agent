# App Troubleshooting Knowledge Agent POC Spec

## 1. Goal

Build a local proof of concept for a chat-based troubleshooting agent that can answer questions about a specific application ID by combining:

- ServiceNow incident exports as tabular data.
- Application architecture documentation from DeepWiki-style Markdown.
- Application infrastructure manifests as JSON.

The POC should demonstrate that the agent can correlate application ownership, components, dependencies, infrastructure, documentation, and incident history to help an engineer or leader understand likely impact, possible root causes, and next troubleshooting steps.

The target local stack is:

- Chainlit for the chat interface.
- FastAPI for backend APIs, ingestion, retrieval, and agent orchestration.
- LangChain for the agent, tool definitions, retrieval composition, and structured responses.
- Neo4j for the application knowledge graph and graph-aware retrieval.
- A vector index for semantic retrieval. For the POC, use Neo4j vector indexes so graph and embeddings live in one local database.

## 2. Pressure Test Summary

### What is strong about the proposed architecture

Neo4j is a good fit for relating heterogeneous operational data. Incidents, app IDs, architecture components, dependencies, owners, clusters, databases, queues, deployments, and documentation chunks are naturally connected entities. Graph traversal is useful when the question is about blast radius, dependency paths, affected upstream or downstream systems, ownership, recent incident patterns, or "what changed around this app?"

LangChain is useful for exposing deterministic tools to an agent. The agent should not directly reason over raw files or ad hoc text dumps. It should call tools such as `get_app_context`, `find_related_incidents`, `search_architecture_docs`, `trace_dependencies`, and `inspect_manifest_resources`.

Chainlit is appropriate for a fast executive demo because it gives a polished chat UI with streaming, message lifecycle hooks, and LangChain callback integration without building a custom frontend.

FastAPI is the right boundary if the goal is more than a demo. It lets the agent become a real service with ingestion endpoints, query endpoints, health checks, reusable APIs, and later authentication.

### Main risks

Do not make Neo4j the only retrieval strategy. Graph traversal is excellent for known relationships, but Markdown architecture pages need semantic search and citations. Incident dumps need structured filtering and aggregation. Infrastructure manifests need deterministic parsing. The better design is graph plus vector plus structured tools.

Do not rely on an LLM to generate arbitrary Cypher in the POC. Natural-language-to-Cypher can be impressive, but it is risky for demos because it may generate invalid or expensive queries. Use parameterized Cypher tools for the core demo paths. Optionally include a guarded read-only Cypher QA tool later.

Do not let Chainlit own business logic. Chainlit should be a chat shell. FastAPI should own ingestion, graph access, retrieval, tool execution, and agent policy. That keeps the POC extensible to Slack, Teams, a custom portal, or API consumers later.

Do not ingest whole Markdown files as single documents. Chunk architecture docs into sections with metadata such as `app_id`, `source_file`, `heading_path`, and `chunk_id`, then attach chunks to graph nodes.

Do not treat every JSON manifest key as a graph node. Extract stable operational entities and relationships first. Keep raw JSON available as evidence, but only promote meaningful concepts such as service, deployment, namespace, cluster, database, queue, topic, bucket, ingress, endpoint, environment, and dependency.

## 3. Recommended Architecture

### Local POC topology

Run four local services:

- `chainlit-ui`: Chainlit app for chat.
- `api`: FastAPI backend for ingestion, agent execution, and retrieval APIs.
- `neo4j`: Neo4j database with graph nodes, relationships, full-text indexes, and vector indexes.
- `seed-data`: local folder mounted into the API container or read directly during ingestion.

For the POC, Chainlit calls FastAPI over HTTP:

- User enters a question in Chainlit.
- Chainlit sends `{session_id, app_id, message}` to FastAPI.
- FastAPI invokes the LangChain agent.
- The agent calls retrieval and graph tools.
- FastAPI returns streamed tokens plus a structured final payload.
- Chainlit renders the final answer, evidence snippets, and source references.

### Why this split

Chainlit is not just a static frontend; it is a Python app framework with its own server lifecycle. Trying to make it behave like a pure React frontend adds friction. For the POC, use Chainlit as a thin Python UI service and keep all durable logic in FastAPI.

This gives a clean future path:

- Replace Chainlit with a custom UI without rewriting the agent.
- Add authentication at the API boundary.
- Add scheduled ingestion jobs.
- Add non-chat workflows such as "generate incident briefing" or "summarize app risk."

## 4. Data Flow

### Ingestion flow

1. Load raw source files from `data/raw`.
2. Normalize each source into canonical records.
3. Upsert graph entities and relationships into Neo4j.
4. Chunk long text sources.
5. Embed text chunks.
6. Store chunks as Neo4j nodes with vector embeddings.
7. Link chunks to application, component, dependency, incident, or manifest nodes.
8. Record ingestion runs and source provenance.

### Query flow

1. User selects or mentions an `app_id`.
2. Backend resolves the app node.
3. Agent builds a retrieval plan.
4. Agent calls tools:
   - app profile lookup,
   - dependency traversal,
   - related incident search,
   - architecture semantic search,
   - infrastructure resource lookup,
   - root cause hypothesis builder.
5. Agent returns:
   - direct answer,
   - likely causes,
   - supporting evidence,
   - confidence level,
   - recommended next checks,
   - source references.

## 5. Graph Data Model

### Core nodes

`Application`

- `app_id`
- `name`
- `business_owner`
- `technical_owner`
- `tier`
- `criticality`
- `description`

`Component`

- `component_id`
- `name`
- `type`
- `app_id`
- examples: api, worker, frontend, batch, database adapter

`Incident`

- `incident_id`
- `number`
- `app_id`
- `opened_at`
- `closed_at`
- `priority`
- `severity`
- `state`
- `short_description`
- `description`
- `resolution_notes`
- `assignment_group`
- `ci_name`

`InfrastructureResource`

- `resource_id`
- `kind`
- `name`
- `environment`
- `namespace`
- `region`
- `cluster`
- `raw_ref`

`Dependency`

- `dependency_id`
- `name`
- `kind`
- `direction`
- examples: database, queue, topic, REST API, internal service, external SaaS

`DocChunk`

- `chunk_id`
- `app_id`
- `source_file`
- `heading_path`
- `text`
- `embedding`
- `source_type`

`Manifest`

- `manifest_id`
- `app_id`
- `source_file`
- `environment`
- `raw_json`
- `ingested_at`

`IngestionRun`

- `run_id`
- `source_type`
- `started_at`
- `completed_at`
- `record_count`
- `status`

### Core relationships

- `(Application)-[:HAS_COMPONENT]->(Component)`
- `(Application)-[:HAS_INCIDENT]->(Incident)`
- `(Application)-[:DEPENDS_ON]->(Dependency)`
- `(Component)-[:DEPENDS_ON]->(Dependency)`
- `(Component)-[:RUNS_ON]->(InfrastructureResource)`
- `(Application)-[:HAS_MANIFEST]->(Manifest)`
- `(Application)-[:HAS_DOC]->(DocChunk)`
- `(Component)-[:MENTIONED_IN]->(DocChunk)`
- `(Incident)-[:MENTIONS]->(Component)`
- `(Incident)-[:RELATED_TO]->(InfrastructureResource)`
- `(InfrastructureResource)-[:CONNECTS_TO]->(Dependency)`
- `(IngestionRun)-[:LOADED]->(Application | Incident | Manifest | DocChunk)`

### Indexes and constraints

Create uniqueness constraints:

- `Application.app_id`
- `Incident.incident_id`
- `Component.component_id`
- `InfrastructureResource.resource_id`
- `Dependency.dependency_id`
- `DocChunk.chunk_id`
- `Manifest.manifest_id`

Create search indexes:

- Full-text index over `Incident.short_description`, `Incident.description`, `Incident.resolution_notes`.
- Full-text index over `DocChunk.text`.
- Vector index over `DocChunk.embedding`.

## 6. Source Normalization

### ServiceNow incident dump

Expected POC input:

- CSV or JSON table export.
- Minimum useful fields:
  - incident number,
  - app ID or CI,
  - opened timestamp,
  - priority/severity,
  - state,
  - short description,
  - full description,
  - close notes or resolution notes,
  - assignment group,
  - affected CI.

Normalization rules:

- Map incident rows to `Incident`.
- Resolve app ID from explicit `app_id`, `business_service`, `cmdb_ci`, or a configurable mapping file.
- Extract component and dependency mentions using deterministic regex/config first.
- Keep original row payload in `raw` metadata for traceability.

### Markdown architecture docs

Expected POC input:

- `data/raw/docs/{app_id}/architecture.md`
- Additional Markdown files allowed under the same app folder.

Normalization rules:

- Parse headings.
- Split chunks by section, then by token budget if a section is too large.
- Store `heading_path`, `source_file`, and line/section metadata.
- Create `DocChunk` nodes.
- Link doc chunks to the app.
- Extract lightweight entities from headings and known patterns:
  - dependencies,
  - databases,
  - queues,
  - external services,
  - environments,
  - endpoints.

### JSON infrastructure manifests

Expected POC input:

- `data/raw/manifests/{app_id}/*.json`

Normalization rules:

- Preserve raw JSON in `Manifest`.
- Extract stable resources into `InfrastructureResource`.
- Link resources to application and components when labels, names, or annotations match.
- Extract dependencies from known fields such as environment variables, connection strings, service bindings, ingress rules, endpoint definitions, queues, topics, database names, and service references.

For the first POC, support a narrow manifest schema even if real enterprise manifests vary. Add a parser interface so future source types can be plugged in.

## 7. Agent Design

### Agent responsibility

The agent should not be a general database chatbot. It should be a troubleshooting assistant with a constrained operating model:

- Identify the application.
- Gather relevant context from graph, incidents, docs, and manifests.
- Correlate evidence across sources.
- Produce a ranked troubleshooting assessment.
- Cite the sources it used.
- Admit missing data.

### System behavior

The agent must:

- Always anchor answers to the requested `app_id`.
- Prefer tool evidence over model prior knowledge.
- Use deterministic graph/query tools before broad semantic search.
- Return source references for claims about incidents, docs, or manifests.
- Distinguish observed facts from hypotheses.
- Avoid claiming root cause certainty unless explicit resolution evidence exists.

### Recommended LangChain shape

Use a LangChain agent created around explicit tools and a structured final response schema.

Core tools:

`get_app_profile(app_id: str)`

- Returns the application node, owners, criticality, components, environments, and known dependencies.

`trace_app_dependencies(app_id: str, depth: int = 2, direction: str = "both")`

- Returns upstream/downstream dependencies and the relationship path.

`find_related_incidents(app_id: str, query: str | None, days: int = 90, limit: int = 10)`

- Runs parameterized Cypher and full-text search against incidents.
- Supports filtering by severity, priority, state, and date range.

`search_architecture_docs(app_id: str, query: str, limit: int = 6)`

- Uses Neo4j vector or hybrid search over `DocChunk`.
- Filters by `app_id`.

`inspect_manifest_resources(app_id: str, environment: str | None = None)`

- Returns parsed infrastructure resources and dependency references.

`build_incident_timeline(app_id: str, incident_number: str | None = None, days: int = 30)`

- Returns recent incidents ordered by time, grouped by symptom and component.

`rank_root_cause_hypotheses(app_id: str, symptoms: list[str], evidence: list[dict])`

- Deterministic helper that scores hypotheses using incident recurrence, dependency overlap, component mentions, manifest resources, and architecture references.

Optional later tool:

`read_only_cypher_query(question: str)`

- Converts natural language to Cypher only for read-only allowlisted patterns.
- Disabled by default for the executive POC unless specifically needed.

## 8. Structured Response Contract

FastAPI should return both streamed text and a final structured payload.

```json
{
  "answer": "string",
  "app_id": "string",
  "summary": "string",
  "likely_causes": [
    {
      "title": "string",
      "confidence": "low | medium | high",
      "why": "string",
      "supporting_evidence_ids": ["string"]
    }
  ],
  "recommended_next_checks": [
    {
      "action": "string",
      "owner_hint": "string | null",
      "source": "incident | docs | manifest | graph | agent"
    }
  ],
  "evidence": [
    {
      "id": "string",
      "source_type": "incident | docs | manifest | graph",
      "source_ref": "string",
      "snippet": "string",
      "url": "string | null"
    }
  ],
  "missing_data": ["string"]
}
```

## 9. FastAPI Contract

### Health

`GET /health`

Returns service status and Neo4j connectivity.

### Ingestion

`POST /ingest/all`

Runs ingestion over local `data/raw`.

`POST /ingest/incidents`

Runs ServiceNow incident ingestion.

`POST /ingest/docs`

Runs Markdown architecture ingestion.

`POST /ingest/manifests`

Runs JSON manifest ingestion.

`GET /ingest/runs`

Returns ingestion history.

### Application context

`GET /apps`

Lists ingested applications.

`GET /apps/{app_id}`

Returns app profile, components, dependencies, resources, doc count, incident count.

`GET /apps/{app_id}/graph`

Returns a small graph payload suitable for visualization.

### Chat

`POST /chat`

Non-streaming agent call.

Request:

```json
{
  "session_id": "string",
  "app_id": "string",
  "message": "string"
}
```

`POST /chat/stream`

Streaming agent call for Chainlit.

## 10. Chainlit UI Requirements

The Chainlit UI should:

- Ask for or infer an `app_id` at chat start.
- Show a small session header with selected app ID and app name.
- Stream the answer from FastAPI.
- Render evidence as expandable side elements or follow-up sections.
- Show suggested prompts for the demo:
  - "What is the current architecture for APP001?"
  - "What recent incidents might explain payment API latency?"
  - "Which dependencies could impact APP001 if the database is degraded?"
  - "Compare the manifest resources with the architecture docs. What looks inconsistent?"
  - "Give me an executive incident briefing for APP001."

For the POC, Chainlit should not directly connect to Neo4j or parse files.

## 11. Demo Dataset

Create at least two sample applications:

`APP001` - customer checkout or payment service.

- Components: frontend, checkout API, payment worker, orders database, payment gateway dependency.
- Incidents:
  - latency spike,
  - failed payment callbacks,
  - database connection pool exhaustion,
  - queue backlog.
- Docs:
  - architecture overview,
  - dependency list,
  - known failure modes,
  - runbook notes.
- Manifest:
  - API deployment,
  - worker deployment,
  - environment variables,
  - database reference,
  - queue/topic reference,
  - ingress endpoint.

`APP002` - inventory or fulfillment service.

- Enough data to demonstrate cross-app dependency impact.
- Include a relationship where `APP001` depends on `APP002` or vice versa.

The demo should include one intentional inconsistency:

- Architecture doc says APP001 uses `orders-db-primary`.
- Manifest points to `orders-db-replica` or an old queue name.
- Recent incident mentions connection failures or stale queue consumer errors.

This gives the agent something concrete to discover.

## 12. Repository Layout

```text
kb-agent/
  README.md
  SPEC.md
  pyproject.toml
  docker-compose.yml
  .env.example
  data/
    raw/
      incidents/
        servicenow_incidents.csv
      docs/
        APP001/
          architecture.md
          runbook.md
        APP002/
          architecture.md
      manifests/
        APP001/
          prod.json
        APP002/
          prod.json
    processed/
  src/
    kb_agent/
      api/
        main.py
        routes_chat.py
        routes_ingest.py
        routes_apps.py
        schemas.py
      agent/
        graph_agent.py
        prompts.py
        response_models.py
        tools.py
      chainlit_app/
        app.py
      ingestion/
        incident_loader.py
        markdown_loader.py
        manifest_loader.py
        pipeline.py
        normalizers.py
      graph/
        neo4j_client.py
        schema.cypher
        repositories.py
      retrieval/
        embeddings.py
        doc_retriever.py
        incident_search.py
      demo/
        seed_data.py
      settings.py
  tests/
    test_ingestion.py
    test_graph_repositories.py
    test_agent_tools.py
```

## 13. Implementation Plan

### Phase 1: Local foundation

- Create Python project.
- Add Docker Compose for Neo4j and local services.
- Add `.env.example`.
- Implement settings loading.
- Implement Neo4j connectivity and schema setup.
- Add sample data.

Acceptance:

- `docker compose up` starts Neo4j.
- `uvicorn kb_agent.api.main:app --reload` starts FastAPI.
- `chainlit run src/kb_agent/chainlit_app/app.py` starts Chainlit.
- `GET /health` confirms Neo4j connectivity.

### Phase 2: Ingestion

- Implement incident CSV loader.
- Implement Markdown loader and chunker.
- Implement JSON manifest loader.
- Implement graph upsert repositories.
- Implement embedding generation and `DocChunk` vector storage.
- Implement `/ingest/all`.

Acceptance:

- Running `/ingest/all` creates app, incident, doc, manifest, resource, and dependency nodes.
- Re-running ingestion is idempotent.
- Neo4j Browser shows relationships for APP001 and APP002.

### Phase 3: Retrieval tools

- Implement app profile lookup.
- Implement dependency traversal.
- Implement incident search.
- Implement architecture doc vector/hybrid search.
- Implement manifest resource lookup.
- Add unit tests for each tool.

Acceptance:

- Each tool can be called directly without the agent.
- Tools return source IDs and snippets.
- Tool results are filtered by `app_id`.

### Phase 4: Agent API

- Implement LangChain agent with explicit tools.
- Add structured response model.
- Add `/chat` and `/chat/stream`.
- Add prompt rules for evidence-grounded troubleshooting.
- Add logging of tool calls and latency.

Acceptance:

- Asking "What could be causing APP001 checkout latency?" returns incidents, manifest resources, and doc evidence.
- The answer separates facts from hypotheses.
- The final payload includes evidence IDs and missing data.

### Phase 5: Chainlit demo UI

- Implement Chainlit app as a thin client to FastAPI.
- Ask user for app ID on session start.
- Stream backend answer.
- Render evidence snippets.
- Add starter prompts.

Acceptance:

- Executive demo can run from one terminal command or documented commands.
- User can select APP001 and ask a troubleshooting question.
- UI response includes concise answer, likely causes, next checks, and evidence.

## 14. Non-Goals For The POC

- Production authentication and authorization.
- Real ServiceNow API integration.
- Real-time event ingestion.
- Full CMDB integration.
- Arbitrary Cypher generation.
- Multi-tenant data isolation.
- Fine-grained document permissions.
- Automated remediation actions.
- Enterprise deployment hardening.

These should be called out explicitly during the showcase as future extensions.

## 15. POC Quality Bar

The POC should be impressive because it is coherent, not because it pretends to be production.

Minimum bar:

- Local startup is reliable.
- Demo data is realistic.
- Agent answers are source-grounded.
- Graph relationships are visible and explainable.
- The app can show an inconsistency or likely root cause that requires correlating at least two data sources.
- Missing data is reported honestly.

## 16. Executive Demo Script

1. Show the three source types:
   - ServiceNow incident table,
   - architecture Markdown,
   - infrastructure JSON manifest.
2. Run ingestion or show ingestion status.
3. Open Neo4j Browser and show APP001 connected to incidents, docs, resources, and dependencies.
4. Open Chainlit.
5. Ask: "For APP001, what are the most likely causes of checkout latency?"
6. Show that the agent cites:
   - recent incidents,
   - architecture dependency notes,
   - manifest resources.
7. Ask: "Do the architecture docs and manifest agree?"
8. Show the intentional mismatch.
9. Ask: "Give me an executive briefing."
10. Show concise impact, likely cause, next checks, owner hints, and confidence.

## 17. Design Decisions For The Coding Agent

Use these defaults unless there is a strong reason to change them:

- Use Python 3.12.
- Use `uv` for local dependency management if available.
- Use Pydantic v2 models.
- Use async FastAPI endpoints.
- Use the official Neo4j Python driver under a small repository layer.
- Use `langchain-neo4j` for vector retrieval where it saves time.
- Keep all Cypher parameterized in application code.
- Keep Chainlit free of graph and ingestion logic.
- Store source provenance on every node created from external data.
- Keep demo data small enough that ingestion completes quickly.

## 18. Suggested Dependencies

Core:

- `fastapi`
- `uvicorn`
- `chainlit`
- `langchain`
- `langchain-openai`
- `langchain-neo4j`
- `neo4j`
- `pydantic`
- `pydantic-settings`
- `python-dotenv`
- `pandas`
- `markdown-it-py`
- `tiktoken`

Testing:

- `pytest`
- `pytest-asyncio`
- `httpx`

Optional:

- `langsmith` for tracing.
- `rich` for local ingestion logging.

## 19. Environment Variables

```text
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
NEO4J_DATABASE=neo4j

API_BASE_URL=http://localhost:8000
DATA_DIR=./data/raw
```

If OpenAI credentials are not available, the implementation can support a local mock mode for ingestion and graph queries, but the agent demo will be materially weaker without embeddings and LLM reasoning.

## 20. Agent Prompt Requirements

The system prompt should include:

- You are an application troubleshooting assistant.
- You answer only from available tool evidence.
- Always scope the answer to the requested app ID.
- Use incidents for historical symptoms and recurrence.
- Use architecture docs for intended design and known failure modes.
- Use manifests for deployed reality.
- Use graph traversal for dependencies and blast radius.
- Separate facts, hypotheses, and recommended checks.
- Cite evidence IDs.
- If data is missing, say what is missing and why it matters.

## 21. Example User Questions

- "What does APP001 depend on?"
- "What recent incidents are similar to payment callback failures?"
- "What could cause checkout latency in APP001?"
- "Which upstream or downstream systems could be affected by APP001?"
- "Do the architecture docs and infrastructure manifest disagree?"
- "What should the on-call engineer check first?"
- "Create an executive briefing for the current APP001 incident."

## 22. Coding Agent Implementation Prompt

Use this prompt to start implementation:

```text
Implement the local POC described in SPEC.md.

Build a Python 3.12 project using Chainlit, FastAPI, LangChain, and Neo4j. Keep Chainlit as a thin chat UI that calls FastAPI. FastAPI owns ingestion, graph access, retrieval tools, and the LangChain agent.

Create the repository layout from the spec. Add Docker Compose for Neo4j. Add realistic seed data for APP001 and APP002 across ServiceNow-style incident CSV, Markdown architecture docs, and JSON manifests. Include one intentional inconsistency between APP001 docs and manifest so the agent can discover it.

Implement idempotent ingestion into Neo4j, including graph constraints, document chunking, embeddings, vector search, and source provenance. Implement deterministic agent tools for app profile, dependency traversal, incident search, architecture document search, and manifest inspection. Implement /health, /ingest/all, /apps, /apps/{app_id}, /chat, and /chat/stream.

Use structured Pydantic response models for final agent answers. The agent must separate facts from hypotheses, cite evidence, report missing data, and keep answers scoped to the selected app_id.

Add focused tests for ingestion, graph repositories, and tool behavior. Document exact local startup and demo commands in README.md.
```
