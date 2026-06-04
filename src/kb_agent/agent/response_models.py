from typing import Literal

from pydantic import BaseModel, Field


EvidenceSource = Literal["incident", "docs", "manifest", "graph"]
Confidence = Literal["low", "medium", "high"]


class EvidenceItem(BaseModel):
    id: str
    source_type: EvidenceSource
    source_ref: str
    snippet: str
    url: str | None = None


class LikelyCause(BaseModel):
    title: str
    confidence: Confidence
    why: str
    supporting_evidence_ids: list[str] = Field(default_factory=list)


class NextCheck(BaseModel):
    action: str
    owner_hint: str | None = None
    source: Literal["incident", "docs", "manifest", "graph", "agent"]


class AgentResponse(BaseModel):
    answer: str
    app_id: str
    summary: str
    likely_causes: list[LikelyCause] = Field(default_factory=list)
    recommended_next_checks: list[NextCheck] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)

