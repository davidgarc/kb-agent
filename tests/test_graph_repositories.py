from pathlib import Path

from kb_agent.graph.repositories import InMemoryGraphRepository
from kb_agent.ingestion.pipeline import IngestionPipeline
from kb_agent.retrieval.embeddings import DeterministicEmbeddingProvider


def seeded_repository() -> InMemoryGraphRepository:
    repository = InMemoryGraphRepository()
    IngestionPipeline(repository, Path("data/raw"), DeterministicEmbeddingProvider(), 128).ingest_all()
    return repository


def test_get_app_profile_returns_graph_context() -> None:
    repository = seeded_repository()

    profile = repository.get_app_profile("APP001")

    assert profile is not None
    assert profile["name"] == "Customer Checkout"
    assert {component["name"] for component in profile["components"]} >= {"checkout-api", "payment-worker"}
    assert any(dependency["name"] == "APP002 inventory-api" for dependency in profile["dependencies"])
    assert profile["doc_count"] >= 7


def test_searches_are_scoped_by_app_id() -> None:
    repository = seeded_repository()
    embedder = DeterministicEmbeddingProvider()

    app001_incidents = repository.search_incidents("APP001", "inventory", limit=10)
    app002_incidents = repository.search_incidents("APP002", "inventory", limit=10)
    docs = repository.search_docs("APP001", "orders-db-primary", embedder.embed_query("orders-db-primary"), limit=3)

    assert all(item["app_id"] == "APP001" for item in app001_incidents)
    assert all(item["app_id"] == "APP002" for item in app002_incidents)
    assert all(item["app_id"] == "APP001" for item in docs)
    assert any("orders-db-primary" in item["text"] for item in docs)

