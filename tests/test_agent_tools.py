from pathlib import Path

from kb_agent.agent.graph_agent import GraphTroubleshootingAgent
from kb_agent.agent.tools import TroubleshootingTools
from kb_agent.graph.repositories import InMemoryGraphRepository
from kb_agent.ingestion.pipeline import IngestionPipeline
from kb_agent.retrieval.embeddings import DeterministicEmbeddingProvider
from kb_agent.settings import Settings


def build_agent() -> GraphTroubleshootingAgent:
    repository = InMemoryGraphRepository()
    embedder = DeterministicEmbeddingProvider()
    IngestionPipeline(repository, Path("data/raw"), embedder, 128).ingest_all()
    settings = Settings(KB_AGENT_GRAPH_MODE="memory", KB_AGENT_USE_OPENROUTER=False)
    return GraphTroubleshootingAgent(TroubleshootingTools(repository, embedder), settings)


def test_tools_return_scoped_evidence() -> None:
    agent = build_agent()
    tools = agent.tools

    profile = tools.get_app_profile("APP001")
    incidents = tools.find_related_incidents("APP001", "latency", limit=5)
    docs = tools.search_architecture_docs("APP001", "checkout queue database", limit=5)
    manifests = tools.inspect_manifest_resources("APP001")

    assert profile["app_id"] == "APP001"
    assert incidents
    assert all(item["app_id"] == "APP001" for item in incidents)
    assert docs
    assert manifests


def test_agent_finds_intentional_manifest_inconsistency() -> None:
    agent = build_agent()

    response = agent.answer("APP001", "Do the architecture docs and manifest agree?")

    assert response.app_id == "APP001"
    assert "orders-db-primary" in response.summary
    assert "orders-db-replica" in response.summary
    assert response.evidence
    assert any(item.source_type == "docs" for item in response.evidence)
    assert any(item.source_type == "manifest" for item in response.evidence)
    assert response.likely_causes[0].title == "Manifest drift from architecture intent"

