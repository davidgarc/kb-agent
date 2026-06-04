from fastapi import APIRouter, Depends, HTTPException

from kb_agent.api.dependencies import AppContainer, get_container
from kb_agent.api.schemas import AppProfile, AppSummary

router = APIRouter(prefix="/apps", tags=["apps"])


@router.get("", response_model=list[AppSummary])
def list_apps(container: AppContainer = Depends(get_container)) -> list[AppSummary]:
    return [AppSummary(**item) for item in container.repository.list_apps()]


@router.get("/{app_id}", response_model=AppProfile)
def get_app(app_id: str, container: AppContainer = Depends(get_container)) -> AppProfile:
    profile = container.repository.get_app_profile(app_id.upper())
    if profile is None:
        raise HTTPException(status_code=404, detail=f"No ingested app found for {app_id.upper()}")
    return AppProfile(**profile)


@router.get("/{app_id}/graph")
def get_app_graph(app_id: str, container: AppContainer = Depends(get_container)) -> dict:
    profile = container.repository.get_app_profile(app_id.upper())
    if profile is None:
        raise HTTPException(status_code=404, detail=f"No ingested app found for {app_id.upper()}")
    nodes = [{"id": app_id.upper(), "label": "Application", "name": profile["name"]}]
    edges = []
    for component in profile["components"]:
        nodes.append({"id": component["component_id"], "label": "Component", "name": component["name"]})
        edges.append({"source": app_id.upper(), "target": component["component_id"], "type": "HAS_COMPONENT"})
    for dependency in profile["dependencies"]:
        nodes.append({"id": dependency["dependency_id"], "label": "Dependency", "name": dependency["name"]})
        edges.append({"source": app_id.upper(), "target": dependency["dependency_id"], "type": "DEPENDS_ON"})
    for resource in profile["resources"]:
        nodes.append({"id": resource["resource_id"], "label": "InfrastructureResource", "name": resource["name"]})
        edges.append({"source": app_id.upper(), "target": resource["resource_id"], "type": "USES_RESOURCE"})
    return {"app_id": app_id.upper(), "nodes": nodes, "edges": edges}

