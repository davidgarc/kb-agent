from kb_agent.graph.repositories import InMemoryGraphRepository
from kb_agent.ingestion.pipeline import IngestionPipeline
from kb_agent.retrieval.embeddings import DeterministicEmbeddingProvider
from kb_agent.settings import get_settings


def build_seeded_memory_repository() -> InMemoryGraphRepository:
    settings = get_settings()
    repository = InMemoryGraphRepository()
    pipeline = IngestionPipeline(
        repository=repository,
        data_dir=settings.data_dir,
        embedder=DeterministicEmbeddingProvider(settings.embedding_dimensions),
        embedding_dimensions=settings.embedding_dimensions,
    )
    pipeline.ingest_all()
    return repository

