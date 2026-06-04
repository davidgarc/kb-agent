from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class NormalizedApplication:
    app_id: str
    name: str
    business_owner: str | None = None
    technical_owner: str | None = None
    tier: str | None = None
    criticality: str | None = None
    description: str | None = None
    source_ref: str = "seed"


@dataclass(frozen=True)
class NormalizedComponent:
    component_id: str
    app_id: str
    name: str
    type: str
    source_ref: str


@dataclass(frozen=True)
class NormalizedDependency:
    dependency_id: str
    app_id: str
    name: str
    kind: str
    direction: str
    source_ref: str
    target_app_id: str | None = None


@dataclass(frozen=True)
class NormalizedResource:
    resource_id: str
    app_id: str
    component_id: str | None
    kind: str
    name: str
    environment: str
    namespace: str | None
    region: str | None
    cluster: str | None
    raw_ref: str
    source_ref: str


@dataclass(frozen=True)
class NormalizedIncident:
    incident_id: str
    number: str
    app_id: str
    opened_at: str
    closed_at: str | None
    priority: str
    severity: str
    state: str
    short_description: str
    description: str
    resolution_notes: str | None
    assignment_group: str | None
    ci_name: str | None
    raw: dict[str, Any]
    source_ref: str


@dataclass(frozen=True)
class NormalizedDocChunk:
    chunk_id: str
    app_id: str
    source_file: str
    heading_path: str
    text: str
    source_type: str
    embedding: list[float] = field(default_factory=list)


@dataclass(frozen=True)
class NormalizedManifest:
    manifest_id: str
    app_id: str
    source_file: str
    environment: str
    raw_json: dict[str, Any]
    ingested_at: str
