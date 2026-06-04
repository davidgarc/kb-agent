import json
from datetime import UTC, datetime
from pathlib import Path

from kb_agent.ingestion.normalizers import (
    NormalizedApplication,
    NormalizedComponent,
    NormalizedDependency,
    NormalizedManifest,
    NormalizedResource,
)


def load_manifests(root: Path) -> tuple[
    list[NormalizedApplication],
    list[NormalizedComponent],
    list[NormalizedDependency],
    list[NormalizedResource],
    list[NormalizedManifest],
]:
    applications: list[NormalizedApplication] = []
    components: list[NormalizedComponent] = []
    dependencies: list[NormalizedDependency] = []
    resources: list[NormalizedResource] = []
    manifests: list[NormalizedManifest] = []

    for app_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        for file_path in sorted(app_dir.glob("*.json")):
            payload = json.loads(file_path.read_text(encoding="utf-8"))
            app_id = payload["app_id"].upper()
            source_ref = str(file_path)
            environment = payload.get("environment", "unknown")
            namespace = payload.get("namespace")
            cluster = payload.get("cluster")

            applications.append(
                NormalizedApplication(
                    app_id=app_id,
                    name=payload.get("name", app_id),
                    business_owner=payload.get("business_owner"),
                    technical_owner=payload.get("technical_owner"),
                    tier=str(payload.get("tier")) if payload.get("tier") is not None else None,
                    criticality=payload.get("criticality"),
                    description=payload.get("description"),
                    source_ref=source_ref,
                )
            )
            manifests.append(
                NormalizedManifest(
                    manifest_id=f"manifest-{app_id}-{environment}",
                    app_id=app_id,
                    source_file=source_ref,
                    environment=environment,
                    raw_json=payload,
                    ingested_at=datetime.now(UTC).isoformat(),
                )
            )

            for component in payload.get("components", []):
                component_id = component.get("component_id") or f"{app_id}-{component['name']}"
                components.append(
                    NormalizedComponent(
                        component_id=component_id,
                        app_id=app_id,
                        name=component["name"],
                        type=component.get("type", "unknown"),
                        source_ref=source_ref,
                    )
                )
                for resource in component.get("resources", []):
                    resource_id = f"resource-{app_id}-{environment}-{resource.get('kind', 'resource')}-{resource['name']}"
                    resources.append(
                        NormalizedResource(
                            resource_id=resource_id,
                            app_id=app_id,
                            component_id=component_id,
                            kind=resource.get("kind", "resource"),
                            name=resource["name"],
                            environment=environment,
                            namespace=namespace,
                            region=resource.get("region"),
                            cluster=cluster,
                            raw_ref=f"{source_ref}#{component['name']}/{resource['name']}",
                            source_ref=source_ref,
                        )
                    )
                for key, value in component.get("env", {}).items():
                    if _looks_like_dependency(value):
                        dep_name = _dependency_name(value)
                        dependencies.append(
                            NormalizedDependency(
                                dependency_id=f"dep-{_slug(dep_name)}",
                                app_id=app_id,
                                name=dep_name,
                                kind=_dependency_kind(key, dep_name),
                                direction="downstream",
                                source_ref=f"{source_ref}#{component['name']}.env.{key}",
                            )
                        )

            for dependency in payload.get("dependencies", []):
                dependencies.append(
                    NormalizedDependency(
                        dependency_id=dependency["dependency_id"],
                        app_id=app_id,
                        name=dependency["name"],
                        kind=dependency.get("kind", "dependency"),
                        direction=dependency.get("direction", "downstream"),
                        target_app_id=dependency.get("target_app_id"),
                        source_ref=source_ref,
                    )
                )

    return applications, components, dependencies, resources, manifests


def _looks_like_dependency(value: str) -> bool:
    return any(token in value.lower() for token in ["db", "queue", "events", "api", "http", "cache"])


def _dependency_name(value: str) -> str:
    if value.startswith("http"):
        host = value.split("//", 1)[-1].split("/", 1)[0]
        return host.split(".", 1)[0]
    return value


def _dependency_kind(key: str, name: str) -> str:
    combined = f"{key} {name}".lower()
    if "db" in combined:
        return "database"
    if "queue" in combined or "events" in combined:
        return "queue"
    if "api" in combined or "http" in combined:
        return "REST API"
    if "cache" in combined:
        return "cache"
    return "dependency"


def _slug(value: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
