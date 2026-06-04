from typing import Any, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from kb_agent.graph.repositories import GraphRepository
from kb_agent.retrieval.embeddings import DeterministicEmbeddingProvider


class AppProfileInput(BaseModel):
    app_id: str


class DependencyInput(BaseModel):
    app_id: str
    depth: int = Field(default=2, ge=1, le=4)
    direction: Literal["upstream", "downstream", "both"] = "both"


class IncidentSearchInput(BaseModel):
    app_id: str
    query: str | None = None
    days: int = Field(default=90, ge=1, le=365)
    limit: int = Field(default=10, ge=1, le=25)


class DocSearchInput(BaseModel):
    app_id: str
    query: str
    limit: int = Field(default=6, ge=1, le=12)


class ManifestInput(BaseModel):
    app_id: str
    environment: str | None = None


class TimelineInput(BaseModel):
    app_id: str
    incident_number: str | None = None
    days: int = Field(default=30, ge=1, le=365)


class HypothesisInput(BaseModel):
    app_id: str
    symptoms: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class TroubleshootingTools:
    def __init__(self, repository: GraphRepository, embedder: DeterministicEmbeddingProvider) -> None:
        self.repository = repository
        self.embedder = embedder

    def get_app_profile(self, app_id: str) -> dict[str, Any]:
        return self.repository.get_app_profile(app_id.upper()) or {"app_id": app_id.upper(), "missing": True}

    def trace_app_dependencies(self, app_id: str, depth: int = 2, direction: str = "both") -> list[dict[str, Any]]:
        return self.repository.trace_dependencies(app_id.upper(), depth=depth, direction=direction)

    def find_related_incidents(self, app_id: str, query: str | None = None, days: int = 90, limit: int = 10) -> list[dict[str, Any]]:
        return self.repository.search_incidents(app_id.upper(), query=query, limit=limit)

    def search_architecture_docs(self, app_id: str, query: str, limit: int = 6) -> list[dict[str, Any]]:
        return self.repository.search_docs(app_id.upper(), query=query, embedding=self.embedder.embed_query(query), limit=limit)

    def inspect_manifest_resources(self, app_id: str, environment: str | None = None) -> list[dict[str, Any]]:
        return self.repository.inspect_manifest(app_id.upper(), environment=environment)

    def build_incident_timeline(self, app_id: str, incident_number: str | None = None, days: int = 30) -> list[dict[str, Any]]:
        incidents = self.find_related_incidents(app_id, query=incident_number, days=days, limit=25) if incident_number else self.find_related_incidents(app_id, days=days, limit=25)
        return sorted(incidents, key=lambda item: item.get("opened_at", ""), reverse=True)

    def rank_root_cause_hypotheses(self, app_id: str, symptoms: list[str], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        text = " ".join(str(item) for item in evidence).lower()
        hypotheses = []
        if "queue" in text or "backlog" in text:
            hypotheses.append({"title": "Payment queue backlog or consumer binding drift", "confidence": "high", "signals": ["queue", "backlog"]})
        if "connection" in text or "orders-db" in text or "database" in text:
            hypotheses.append({"title": "Orders database connection pool pressure", "confidence": "high", "signals": ["database", "connection"]})
        if "inventory" in text or "app002" in text:
            hypotheses.append({"title": "Inventory API latency affecting checkout validation", "confidence": "medium", "signals": ["inventory", "APP002"]})
        if "gateway" in text or "callback" in text:
            hypotheses.append({"title": "Payment gateway callback retry pressure", "confidence": "medium", "signals": ["gateway", "callback"]})
        return hypotheses or [{"title": "Insufficient evidence for a ranked hypothesis", "confidence": "low", "signals": []}]

    def as_langchain_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool.from_function(self.get_app_profile, name="get_app_profile", description="Return owners, criticality, components, environments, and dependencies for an app.", args_schema=AppProfileInput),
            StructuredTool.from_function(self.trace_app_dependencies, name="trace_app_dependencies", description="Return dependency paths for an app.", args_schema=DependencyInput),
            StructuredTool.from_function(self.find_related_incidents, name="find_related_incidents", description="Search recent incidents for an app.", args_schema=IncidentSearchInput),
            StructuredTool.from_function(self.search_architecture_docs, name="search_architecture_docs", description="Search architecture docs and runbooks for an app.", args_schema=DocSearchInput),
            StructuredTool.from_function(self.inspect_manifest_resources, name="inspect_manifest_resources", description="Inspect manifest resources and raw deployed bindings for an app.", args_schema=ManifestInput),
            StructuredTool.from_function(self.build_incident_timeline, name="build_incident_timeline", description="Build a recent incident timeline for an app.", args_schema=TimelineInput),
            StructuredTool.from_function(self.rank_root_cause_hypotheses, name="rank_root_cause_hypotheses", description="Rank likely root cause hypotheses from gathered evidence.", args_schema=HypothesisInput),
        ]

