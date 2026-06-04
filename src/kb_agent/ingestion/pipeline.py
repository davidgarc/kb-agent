from dataclasses import dataclass, field
from pathlib import Path

from kb_agent.graph.repositories import GraphRepository
from kb_agent.ingestion.incident_loader import load_incidents
from kb_agent.ingestion.manifest_loader import load_manifests
from kb_agent.ingestion.markdown_loader import load_markdown_docs
from kb_agent.retrieval.embeddings import DeterministicEmbeddingProvider


@dataclass
class IngestionResult:
    run_id: str
    source_type: str
    record_count: int
    status: str = "completed"
    details: dict[str, int] = field(default_factory=dict)


class IngestionPipeline:
    def __init__(self, repository: GraphRepository, data_dir: Path, embedder: DeterministicEmbeddingProvider, embedding_dimensions: int = 128) -> None:
        self.repository = repository
        self.data_dir = data_dir
        self.embedder = embedder
        self.embedding_dimensions = embedding_dimensions

    def setup(self) -> None:
        self.repository.setup_schema(self.embedding_dimensions)

    def ingest_all(self) -> IngestionResult:
        self.setup()
        run_id = self.repository.create_ingestion_run("all")
        details: dict[str, int] = {}
        record_count = 0
        try:
            manifest_result = self._ingest_manifests(run_id)
            incident_result = self._ingest_incidents(run_id)
            docs_result = self._ingest_docs(run_id)
            details.update(manifest_result)
            details.update(incident_result)
            details.update(docs_result)
            record_count = sum(details.values())
            self.repository.complete_ingestion_run(run_id, record_count)
            return IngestionResult(run_id=run_id, source_type="all", record_count=record_count, details=details)
        except Exception:
            self.repository.complete_ingestion_run(run_id, record_count, status="failed")
            raise

    def ingest_incidents(self) -> IngestionResult:
        self.setup()
        run_id = self.repository.create_ingestion_run("incidents")
        details = self._ingest_incidents(run_id)
        record_count = sum(details.values())
        self.repository.complete_ingestion_run(run_id, record_count)
        return IngestionResult(run_id=run_id, source_type="incidents", record_count=record_count, details=details)

    def ingest_docs(self) -> IngestionResult:
        self.setup()
        run_id = self.repository.create_ingestion_run("docs")
        details = self._ingest_docs(run_id)
        record_count = sum(details.values())
        self.repository.complete_ingestion_run(run_id, record_count)
        return IngestionResult(run_id=run_id, source_type="docs", record_count=record_count, details=details)

    def ingest_manifests(self) -> IngestionResult:
        self.setup()
        run_id = self.repository.create_ingestion_run("manifests")
        details = self._ingest_manifests(run_id)
        record_count = sum(details.values())
        self.repository.complete_ingestion_run(run_id, record_count)
        return IngestionResult(run_id=run_id, source_type="manifests", record_count=record_count, details=details)

    def _ingest_incidents(self, run_id: str) -> dict[str, int]:
        count = 0
        for csv_path in sorted((self.data_dir / "incidents").glob("*.csv")):
            for incident in load_incidents(csv_path):
                self.repository.upsert_incident(incident, run_id)
                count += 1
        return {"incidents": count}

    def _ingest_docs(self, run_id: str) -> dict[str, int]:
        chunks, dependencies = load_markdown_docs(self.data_dir / "docs", self.embedder)
        for chunk in chunks:
            self.repository.upsert_doc_chunk(chunk, run_id)
        for dependency in dependencies:
            self.repository.upsert_dependency(dependency, run_id)
        return {"doc_chunks": len(chunks), "doc_dependencies": len(dependencies)}

    def _ingest_manifests(self, run_id: str) -> dict[str, int]:
        applications, components, dependencies, resources, manifests = load_manifests(self.data_dir / "manifests")
        for application in applications:
            self.repository.upsert_application(application, run_id)
        for component in components:
            self.repository.upsert_component(component, run_id)
        for dependency in dependencies:
            self.repository.upsert_dependency(dependency, run_id)
        for resource in resources:
            self.repository.upsert_resource(resource, run_id)
        for manifest in manifests:
            self.repository.upsert_manifest(manifest, run_id)
        return {
            "applications": len(applications),
            "components": len(components),
            "manifest_dependencies": len(dependencies),
            "resources": len(resources),
            "manifests": len(manifests),
        }
