from pathlib import Path

from kb_agent.graph.repositories import InMemoryGraphRepository
from kb_agent.ingestion.pipeline import IngestionPipeline
from kb_agent.retrieval.embeddings import DeterministicEmbeddingProvider


def test_ingest_all_is_idempotent() -> None:
    repository = InMemoryGraphRepository()
    pipeline = IngestionPipeline(repository, Path("data/raw"), DeterministicEmbeddingProvider(), 128)

    first = pipeline.ingest_all()
    second = pipeline.ingest_all()

    assert first.status == "completed"
    assert second.status == "completed"
    assert len(repository.apps) == 2
    assert len(repository.incidents) == 6
    assert len(repository.manifests) == 2
    assert len(repository.docs) >= 7
    assert repository.get_app_profile("APP001")["incident_count"] == 4


def test_markdown_chunks_include_provenance_and_embeddings() -> None:
    repository = InMemoryGraphRepository()
    pipeline = IngestionPipeline(repository, Path("data/raw"), DeterministicEmbeddingProvider(), 128)
    pipeline.ingest_all()

    chunk = next(item for item in repository.docs.values() if item["app_id"] == "APP001")

    assert chunk["source_file"].endswith(".md")
    assert "line" in chunk["heading_path"]
    assert len(chunk["embedding"]) == 128
    assert chunk["source_type"] == "docs"

