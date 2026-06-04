from fastapi import FastAPI

from kb_agent.api.dependencies import get_container
from kb_agent.api.routes_apps import router as apps_router
from kb_agent.api.routes_chat import router as chat_router
from kb_agent.api.routes_ingest import router as ingest_router
from kb_agent.api.schemas import HealthResponse

app = FastAPI(title="KB Agent API", version="0.1.0")
app.include_router(ingest_router)
app.include_router(apps_router)
app.include_router(chat_router)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    container = get_container()
    connected = container.repository.health()
    message = "Neo4j connected" if container.neo4j_connected else "Using deterministic in-memory graph fallback"
    return HealthResponse(status="ok", neo4j_connected=connected and container.neo4j_connected, graph_mode=container.graph_mode, message=message)

