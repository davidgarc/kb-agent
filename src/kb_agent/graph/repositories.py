import json
import re
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any, Protocol

from neo4j import Driver

from kb_agent.ingestion.normalizers import (
    NormalizedApplication,
    NormalizedComponent,
    NormalizedDependency,
    NormalizedDocChunk,
    NormalizedIncident,
    NormalizedManifest,
    NormalizedResource,
)
from kb_agent.retrieval.embeddings import cosine_similarity


class GraphRepository(Protocol):
    def setup_schema(self, embedding_dimensions: int) -> None: ...
    def create_ingestion_run(self, source_type: str, status: str = "running") -> str: ...
    def complete_ingestion_run(self, run_id: str, record_count: int, status: str = "completed") -> None: ...
    def upsert_application(self, app: NormalizedApplication, run_id: str | None = None) -> None: ...
    def upsert_component(self, component: NormalizedComponent, run_id: str | None = None) -> None: ...
    def upsert_dependency(self, dependency: NormalizedDependency, run_id: str | None = None) -> None: ...
    def upsert_resource(self, resource: NormalizedResource, run_id: str | None = None) -> None: ...
    def upsert_incident(self, incident: NormalizedIncident, run_id: str | None = None) -> None: ...
    def upsert_doc_chunk(self, chunk: NormalizedDocChunk, run_id: str | None = None) -> None: ...
    def upsert_manifest(self, manifest: NormalizedManifest, run_id: str | None = None) -> None: ...
    def health(self) -> bool: ...
    def list_apps(self) -> list[dict[str, Any]]: ...
    def get_app_profile(self, app_id: str) -> dict[str, Any] | None: ...
    def trace_dependencies(self, app_id: str, depth: int = 2, direction: str = "both") -> list[dict[str, Any]]: ...
    def search_incidents(self, app_id: str, query: str | None = None, limit: int = 10) -> list[dict[str, Any]]: ...
    def search_docs(self, app_id: str, query: str, embedding: list[float], limit: int = 6) -> list[dict[str, Any]]: ...
    def inspect_manifest(self, app_id: str, environment: str | None = None) -> list[dict[str, Any]]: ...
    def ingestion_runs(self) -> list[dict[str, Any]]: ...


class Neo4jGraphRepository:
    def __init__(self, driver: Driver, database: str = "neo4j") -> None:
        self.driver = driver
        self.database = database

    def health(self) -> bool:
        try:
            self.driver.verify_connectivity()
        except Exception:
            return False
        return True

    def setup_schema(self, embedding_dimensions: int) -> None:
        statements = [
            "CREATE CONSTRAINT application_app_id IF NOT EXISTS FOR (n:Application) REQUIRE n.app_id IS UNIQUE",
            "CREATE CONSTRAINT incident_incident_id IF NOT EXISTS FOR (n:Incident) REQUIRE n.incident_id IS UNIQUE",
            "CREATE CONSTRAINT component_component_id IF NOT EXISTS FOR (n:Component) REQUIRE n.component_id IS UNIQUE",
            "CREATE CONSTRAINT resource_resource_id IF NOT EXISTS FOR (n:InfrastructureResource) REQUIRE n.resource_id IS UNIQUE",
            "CREATE CONSTRAINT dependency_dependency_id IF NOT EXISTS FOR (n:Dependency) REQUIRE n.dependency_id IS UNIQUE",
            "CREATE CONSTRAINT doc_chunk_chunk_id IF NOT EXISTS FOR (n:DocChunk) REQUIRE n.chunk_id IS UNIQUE",
            "CREATE CONSTRAINT manifest_manifest_id IF NOT EXISTS FOR (n:Manifest) REQUIRE n.manifest_id IS UNIQUE",
            "CREATE CONSTRAINT ingestion_run_run_id IF NOT EXISTS FOR (n:IngestionRun) REQUIRE n.run_id IS UNIQUE",
            "CREATE FULLTEXT INDEX incident_text IF NOT EXISTS FOR (n:Incident) ON EACH [n.short_description, n.description, n.resolution_notes]",
            "CREATE FULLTEXT INDEX docchunk_text IF NOT EXISTS FOR (n:DocChunk) ON EACH [n.text]",
            (
                "CREATE VECTOR INDEX docchunk_embedding IF NOT EXISTS FOR (n:DocChunk) ON (n.embedding) "
                f"OPTIONS {{indexConfig: {{`vector.dimensions`: {int(embedding_dimensions)}, `vector.similarity_function`: 'cosine'}}}}"
            ),
        ]
        with self.driver.session(database=self.database) as session:
            for statement in statements:
                session.run(statement)

    def create_ingestion_run(self, source_type: str, status: str = "running") -> str:
        run_id = str(uuid.uuid4())
        self._run(
            """
            MERGE (r:IngestionRun {run_id: $run_id})
            SET r.source_type = $source_type, r.started_at = $started_at, r.status = $status, r.record_count = 0
            """,
            run_id=run_id,
            source_type=source_type,
            started_at=datetime.now(UTC).isoformat(),
            status=status,
        )
        return run_id

    def complete_ingestion_run(self, run_id: str, record_count: int, status: str = "completed") -> None:
        self._run(
            """
            MATCH (r:IngestionRun {run_id: $run_id})
            SET r.completed_at = $completed_at, r.record_count = $record_count, r.status = $status
            """,
            run_id=run_id,
            completed_at=datetime.now(UTC).isoformat(),
            record_count=record_count,
            status=status,
        )

    def upsert_application(self, app: NormalizedApplication, run_id: str | None = None) -> None:
        self._run(
            """
            MERGE (a:Application {app_id: $app_id})
            SET a.name = $name, a.business_owner = $business_owner, a.technical_owner = $technical_owner,
                a.tier = $tier, a.criticality = $criticality, a.description = $description,
                a.source_type = 'manifest', a.source_ref = $source_ref, a.updated_at = $updated_at
            WITH a
            OPTIONAL MATCH (r:IngestionRun {run_id: $run_id})
            FOREACH (_ IN CASE WHEN r IS NULL THEN [] ELSE [1] END | MERGE (r)-[:LOADED]->(a))
            """,
            **app.__dict__,
            updated_at=datetime.now(UTC).isoformat(),
            run_id=run_id,
        )

    def upsert_component(self, component: NormalizedComponent, run_id: str | None = None) -> None:
        self._run(
            """
            MATCH (a:Application {app_id: $app_id})
            MERGE (c:Component {component_id: $component_id})
            SET c.name = $name, c.type = $type, c.app_id = $app_id, c.source_type = 'manifest', c.source_ref = $source_ref
            MERGE (a)-[:HAS_COMPONENT]->(c)
            WITH c
            OPTIONAL MATCH (r:IngestionRun {run_id: $run_id})
            FOREACH (_ IN CASE WHEN r IS NULL THEN [] ELSE [1] END | MERGE (r)-[:LOADED]->(c))
            """,
            **component.__dict__,
            run_id=run_id,
        )

    def upsert_dependency(self, dependency: NormalizedDependency, run_id: str | None = None) -> None:
        self._run(
            """
            MATCH (a:Application {app_id: $app_id})
            MERGE (d:Dependency {dependency_id: $dependency_id})
            SET d.name = $name, d.kind = $kind, d.direction = $direction, d.source_ref = $source_ref,
                d.target_app_id = $target_app_id, d.source_type = 'manifest'
            MERGE (a)-[:DEPENDS_ON {direction: $direction}]->(d)
            WITH d
            OPTIONAL MATCH (r:IngestionRun {run_id: $run_id})
            FOREACH (_ IN CASE WHEN r IS NULL THEN [] ELSE [1] END | MERGE (r)-[:LOADED]->(d))
            """,
            **dependency.__dict__,
            run_id=run_id,
        )

    def upsert_resource(self, resource: NormalizedResource, run_id: str | None = None) -> None:
        self._run(
            """
            MATCH (a:Application {app_id: $app_id})
            MERGE (i:InfrastructureResource {resource_id: $resource_id})
            SET i.kind = $kind, i.name = $name, i.environment = $environment, i.namespace = $namespace,
                i.region = $region, i.cluster = $cluster, i.raw_ref = $raw_ref, i.source_ref = $source_ref,
                i.source_type = 'manifest'
            MERGE (a)-[:USES_RESOURCE]->(i)
            WITH i
            OPTIONAL MATCH (c:Component {component_id: $component_id})
            FOREACH (_ IN CASE WHEN c IS NULL THEN [] ELSE [1] END | MERGE (c)-[:RUNS_ON]->(i))
            WITH i
            OPTIONAL MATCH (r:IngestionRun {run_id: $run_id})
            FOREACH (_ IN CASE WHEN r IS NULL THEN [] ELSE [1] END | MERGE (r)-[:LOADED]->(i))
            """,
            **resource.__dict__,
            run_id=run_id,
        )

    def upsert_incident(self, incident: NormalizedIncident, run_id: str | None = None) -> None:
        self._run(
            """
            MATCH (a:Application {app_id: $app_id})
            MERGE (i:Incident {incident_id: $incident_id})
            SET i.number = $number, i.app_id = $app_id, i.opened_at = $opened_at, i.closed_at = $closed_at,
                i.priority = $priority, i.severity = $severity, i.state = $state,
                i.short_description = $short_description, i.description = $description,
                i.resolution_notes = $resolution_notes, i.assignment_group = $assignment_group,
                i.ci_name = $ci_name, i.raw = $raw, i.source_ref = $source_ref, i.source_type = 'incident'
            MERGE (a)-[:HAS_INCIDENT]->(i)
            WITH i
            OPTIONAL MATCH (r:IngestionRun {run_id: $run_id})
            FOREACH (_ IN CASE WHEN r IS NULL THEN [] ELSE [1] END | MERGE (r)-[:LOADED]->(i))
            """,
            **{**incident.__dict__, "raw": json.dumps(incident.raw)},
            run_id=run_id,
        )

    def upsert_doc_chunk(self, chunk: NormalizedDocChunk, run_id: str | None = None) -> None:
        self._run(
            """
            MATCH (a:Application {app_id: $app_id})
            MERGE (d:DocChunk {chunk_id: $chunk_id})
            SET d.app_id = $app_id, d.source_file = $source_file, d.heading_path = $heading_path,
                d.text = $text, d.embedding = $embedding, d.source_type = $source_type
            MERGE (a)-[:HAS_DOC]->(d)
            WITH d
            OPTIONAL MATCH (r:IngestionRun {run_id: $run_id})
            FOREACH (_ IN CASE WHEN r IS NULL THEN [] ELSE [1] END | MERGE (r)-[:LOADED]->(d))
            """,
            **chunk.__dict__,
            run_id=run_id,
        )

    def upsert_manifest(self, manifest: NormalizedManifest, run_id: str | None = None) -> None:
        self._run(
            """
            MATCH (a:Application {app_id: $app_id})
            MERGE (m:Manifest {manifest_id: $manifest_id})
            SET m.app_id = $app_id, m.source_file = $source_file, m.environment = $environment,
                m.raw_json = $raw_json, m.ingested_at = $ingested_at, m.source_type = 'manifest'
            MERGE (a)-[:HAS_MANIFEST]->(m)
            WITH m
            OPTIONAL MATCH (r:IngestionRun {run_id: $run_id})
            FOREACH (_ IN CASE WHEN r IS NULL THEN [] ELSE [1] END | MERGE (r)-[:LOADED]->(m))
            """,
            **{**manifest.__dict__, "raw_json": json.dumps(manifest.raw_json, sort_keys=True)},
            run_id=run_id,
        )

    def list_apps(self) -> list[dict[str, Any]]:
        return self._records(
            """
            MATCH (a:Application)
            RETURN a.app_id AS app_id, a.name AS name, a.business_owner AS business_owner,
                   a.technical_owner AS technical_owner, a.tier AS tier, a.criticality AS criticality
            ORDER BY a.app_id
            """
        )

    def get_app_profile(self, app_id: str) -> dict[str, Any] | None:
        rows = self._records(
            """
            MATCH (a:Application {app_id: $app_id})
            OPTIONAL MATCH (a)-[:HAS_COMPONENT]->(c:Component)
            OPTIONAL MATCH (a)-[:DEPENDS_ON]->(d:Dependency)
            OPTIONAL MATCH (a)-[:USES_RESOURCE]->(r:InfrastructureResource)
            OPTIONAL MATCH (a)-[:HAS_INCIDENT]->(i:Incident)
            OPTIONAL MATCH (a)-[:HAS_DOC]->(doc:DocChunk)
            RETURN properties(a) AS app,
                   collect(DISTINCT properties(c)) AS components,
                   collect(DISTINCT properties(d)) AS dependencies,
                   collect(DISTINCT properties(r)) AS resources,
                   count(DISTINCT i) AS incident_count,
                   count(DISTINCT doc) AS doc_count
            """,
            app_id=app_id,
        )
        if not rows:
            return None
        row = rows[0]
        return {**row["app"], "components": _clean(row["components"]), "dependencies": _clean(row["dependencies"]), "resources": _clean(row["resources"]), "incident_count": row["incident_count"], "doc_count": row["doc_count"]}

    def trace_dependencies(self, app_id: str, depth: int = 2, direction: str = "both") -> list[dict[str, Any]]:
        return self._records(
            """
            MATCH (a:Application {app_id: $app_id})-[rel:DEPENDS_ON]->(d:Dependency)
            RETURN d.dependency_id AS dependency_id, d.name AS name, d.kind AS kind, d.direction AS direction,
                   d.target_app_id AS target_app_id, 'Application DEPENDS_ON Dependency' AS path
            ORDER BY d.name
            """,
            app_id=app_id,
        )

    def search_incidents(self, app_id: str, query: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        terms = _terms(query or "")
        rows = self._records(
            """
            MATCH (:Application {app_id: $app_id})-[:HAS_INCIDENT]->(i:Incident)
            RETURN properties(i) AS incident
            ORDER BY i.opened_at DESC
            LIMIT $limit
            """,
            app_id=app_id,
            limit=limit * 3,
        )
        incidents = [row["incident"] for row in rows]
        if terms:
            incidents = [item for item in incidents if _matches_terms(item, terms)]
        return incidents[:limit]

    def search_docs(self, app_id: str, query: str, embedding: list[float], limit: int = 6) -> list[dict[str, Any]]:
        rows = self._records(
            """
            MATCH (:Application {app_id: $app_id})-[:HAS_DOC]->(d:DocChunk)
            RETURN properties(d) AS doc
            """,
            app_id=app_id,
        )
        docs = []
        terms = _terms(query)
        for row in rows:
            doc = row["doc"]
            score = cosine_similarity(embedding, doc.get("embedding") or [])
            if terms and _matches_text(doc.get("text", ""), terms):
                score += 0.25
            docs.append({**doc, "score": score})
        return sorted(docs, key=lambda item: item["score"], reverse=True)[:limit]

    def inspect_manifest(self, app_id: str, environment: str | None = None) -> list[dict[str, Any]]:
        return self._records(
            """
            MATCH (:Application {app_id: $app_id})-[:HAS_MANIFEST]->(m:Manifest)
            WHERE $environment IS NULL OR m.environment = $environment
            OPTIONAL MATCH (:Application {app_id: $app_id})-[:USES_RESOURCE]->(r:InfrastructureResource)
            RETURN properties(m) AS manifest, collect(DISTINCT properties(r)) AS resources
            ORDER BY manifest.environment
            """,
            app_id=app_id,
            environment=environment,
        )

    def ingestion_runs(self) -> list[dict[str, Any]]:
        return self._records(
            """
            MATCH (r:IngestionRun)
            RETURN properties(r) AS run
            ORDER BY r.started_at DESC
            LIMIT 20
            """
        )

    def _run(self, statement: str, **parameters: Any) -> None:
        with self.driver.session(database=self.database) as session:
            session.run(statement, parameters)

    def _records(self, statement: str, **parameters: Any) -> list[dict[str, Any]]:
        with self.driver.session(database=self.database) as session:
            result = session.run(statement, parameters)
            return [dict(record) for record in result]


class InMemoryGraphRepository:
    def __init__(self) -> None:
        self.apps: dict[str, dict[str, Any]] = {}
        self.components: dict[str, dict[str, Any]] = {}
        self.dependencies: dict[str, dict[str, Any]] = {}
        self.resources: dict[str, dict[str, Any]] = {}
        self.incidents: dict[str, dict[str, Any]] = {}
        self.docs: dict[str, dict[str, Any]] = {}
        self.manifests: dict[str, dict[str, Any]] = {}
        self.runs: dict[str, dict[str, Any]] = {}

    def health(self) -> bool:
        return True

    def setup_schema(self, embedding_dimensions: int) -> None:
        return None

    def create_ingestion_run(self, source_type: str, status: str = "running") -> str:
        run_id = str(uuid.uuid4())
        self.runs[run_id] = {"run_id": run_id, "source_type": source_type, "started_at": datetime.now(UTC).isoformat(), "status": status, "record_count": 0}
        return run_id

    def complete_ingestion_run(self, run_id: str, record_count: int, status: str = "completed") -> None:
        self.runs[run_id].update({"completed_at": datetime.now(UTC).isoformat(), "record_count": record_count, "status": status})

    def upsert_application(self, app: NormalizedApplication, run_id: str | None = None) -> None:
        self.apps[app.app_id] = {**self.apps.get(app.app_id, {}), **app.__dict__, "source_type": "manifest"}

    def upsert_component(self, component: NormalizedComponent, run_id: str | None = None) -> None:
        self.components[component.component_id] = {**component.__dict__, "source_type": "manifest"}

    def upsert_dependency(self, dependency: NormalizedDependency, run_id: str | None = None) -> None:
        self.dependencies[dependency.dependency_id] = {**dependency.__dict__, "source_type": "manifest"}

    def upsert_resource(self, resource: NormalizedResource, run_id: str | None = None) -> None:
        self.resources[resource.resource_id] = {**resource.__dict__, "source_type": "manifest"}

    def upsert_incident(self, incident: NormalizedIncident, run_id: str | None = None) -> None:
        self.incidents[incident.incident_id] = {**incident.__dict__, "source_type": "incident"}

    def upsert_doc_chunk(self, chunk: NormalizedDocChunk, run_id: str | None = None) -> None:
        self.docs[chunk.chunk_id] = {**chunk.__dict__}

    def upsert_manifest(self, manifest: NormalizedManifest, run_id: str | None = None) -> None:
        self.manifests[manifest.manifest_id] = {**manifest.__dict__, "source_type": "manifest"}

    def list_apps(self) -> list[dict[str, Any]]:
        return sorted(self.apps.values(), key=lambda app: app["app_id"])

    def get_app_profile(self, app_id: str) -> dict[str, Any] | None:
        app = self.apps.get(app_id)
        if not app:
            return None
        components = [item for item in self.components.values() if item["app_id"] == app_id]
        dependencies = [item for item in self.dependencies.values() if item["app_id"] == app_id]
        resources = [item for item in self.resources.values() if item["app_id"] == app_id]
        return {
            **app,
            "components": components,
            "dependencies": dependencies,
            "resources": resources,
            "incident_count": len([item for item in self.incidents.values() if item["app_id"] == app_id]),
            "doc_count": len([item for item in self.docs.values() if item["app_id"] == app_id]),
        }

    def trace_dependencies(self, app_id: str, depth: int = 2, direction: str = "both") -> list[dict[str, Any]]:
        return [
            {**dependency, "path": "Application DEPENDS_ON Dependency"}
            for dependency in sorted(self.dependencies.values(), key=lambda item: item["name"])
            if dependency["app_id"] == app_id and (direction == "both" or dependency.get("direction") == direction)
        ]

    def search_incidents(self, app_id: str, query: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        terms = _terms(query or "")
        incidents = [item for item in self.incidents.values() if item["app_id"] == app_id]
        if terms:
            incidents = [item for item in incidents if _matches_terms(item, terms)]
        return sorted(incidents, key=lambda item: item["opened_at"], reverse=True)[:limit]

    def search_docs(self, app_id: str, query: str, embedding: list[float], limit: int = 6) -> list[dict[str, Any]]:
        terms = _terms(query)
        docs = []
        for doc in self.docs.values():
            if doc["app_id"] != app_id:
                continue
            score = cosine_similarity(embedding, doc.get("embedding", []))
            if terms and _matches_text(doc["text"], terms):
                score += 0.25
            docs.append({**doc, "score": score})
        return sorted(docs, key=lambda item: item["score"], reverse=True)[:limit]

    def inspect_manifest(self, app_id: str, environment: str | None = None) -> list[dict[str, Any]]:
        resources_by_app = [resource for resource in self.resources.values() if resource["app_id"] == app_id]
        rows = []
        for manifest in self.manifests.values():
            if manifest["app_id"] != app_id:
                continue
            if environment and manifest["environment"] != environment:
                continue
            rows.append({"manifest": manifest, "resources": resources_by_app})
        return rows

    def ingestion_runs(self) -> list[dict[str, Any]]:
        return sorted(self.runs.values(), key=lambda run: run["started_at"], reverse=True)


def _terms(query: str) -> list[str]:
    return [term for term in re.findall(r"[a-zA-Z0-9_.-]+", query.lower()) if len(term) > 2]


def _matches_terms(item: dict[str, Any], terms: list[str]) -> bool:
    haystack = " ".join(str(item.get(key, "")) for key in ["short_description", "description", "resolution_notes", "ci_name", "number"]).lower()
    return any(term in haystack for term in terms)


def _matches_text(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return any(term in lower for term in terms)


def _clean(values: list[dict[str, Any] | None]) -> list[dict[str, Any]]:
    return [value for value in values if value]
