from pydantic import BaseModel, Field

from kb_agent.agent.response_models import AgentResponse


class HealthResponse(BaseModel):
    status: str
    neo4j_connected: bool
    graph_mode: str
    message: str


class IngestResponse(BaseModel):
    run_id: str
    status: str
    source_type: str
    record_count: int
    details: dict[str, int] = Field(default_factory=dict)


class AppSummary(BaseModel):
    app_id: str
    name: str
    business_owner: str | None = None
    technical_owner: str | None = None
    tier: str | None = None
    criticality: str | None = None


class AppProfile(BaseModel):
    app_id: str
    name: str
    business_owner: str | None = None
    technical_owner: str | None = None
    tier: str | None = None
    criticality: str | None = None
    description: str | None = None
    components: list[dict] = Field(default_factory=list)
    dependencies: list[dict] = Field(default_factory=list)
    resources: list[dict] = Field(default_factory=list)
    incident_count: int = 0
    doc_count: int = 0


class ChatRequest(BaseModel):
    session_id: str
    app_id: str
    message: str


class ChatResponse(BaseModel):
    session_id: str
    result: AgentResponse

