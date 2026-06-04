from fastapi import APIRouter, Depends

from kb_agent.api.dependencies import AppContainer, get_container
from kb_agent.api.schemas import IngestResponse

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post("/all", response_model=IngestResponse)
def ingest_all(container: AppContainer = Depends(get_container)) -> IngestResponse:
    result = container.pipeline.ingest_all()
    return IngestResponse(**result.__dict__)


@router.post("/incidents", response_model=IngestResponse)
def ingest_incidents(container: AppContainer = Depends(get_container)) -> IngestResponse:
    result = container.pipeline.ingest_incidents()
    return IngestResponse(**result.__dict__)


@router.post("/docs", response_model=IngestResponse)
def ingest_docs(container: AppContainer = Depends(get_container)) -> IngestResponse:
    result = container.pipeline.ingest_docs()
    return IngestResponse(**result.__dict__)


@router.post("/manifests", response_model=IngestResponse)
def ingest_manifests(container: AppContainer = Depends(get_container)) -> IngestResponse:
    result = container.pipeline.ingest_manifests()
    return IngestResponse(**result.__dict__)


@router.get("/runs")
def ingestion_runs(container: AppContainer = Depends(get_container)) -> list[dict]:
    return container.repository.ingestion_runs()

