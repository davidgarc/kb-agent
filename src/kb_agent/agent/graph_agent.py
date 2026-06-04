import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from kb_agent.agent.prompts import SYSTEM_PROMPT
from kb_agent.agent.response_models import AgentResponse, EvidenceItem, LikelyCause, NextCheck
from kb_agent.agent.tools import TroubleshootingTools
from kb_agent.settings import Settings, get_settings


class GraphTroubleshootingAgent:
    def __init__(self, tools: TroubleshootingTools, settings: Settings | None = None) -> None:
        self.tools = tools
        self.langchain_tools = tools.as_langchain_tools()
        self.settings = settings or get_settings()
        self.llm = self._build_llm()

    def answer(self, app_id: str, message: str) -> AgentResponse:
        scoped_app_id = app_id.upper()
        query = _query_for_message(message)
        profile = self.tools.get_app_profile(scoped_app_id)
        if profile.get("missing"):
            return AgentResponse(
                app_id=scoped_app_id,
                answer=f"I do not have ingested data for {scoped_app_id}.",
                summary=f"No application profile is available for {scoped_app_id}.",
                missing_data=["Application profile, incidents, docs, and manifests are missing for the selected app_id."],
            )

        dependencies = self.tools.trace_app_dependencies(scoped_app_id)
        incidents = self.tools.find_related_incidents(scoped_app_id, query=query, limit=8)
        docs = self.tools.search_architecture_docs(scoped_app_id, query=message, limit=6)
        manifests = self.tools.inspect_manifest_resources(scoped_app_id)
        evidence = _build_evidence(scoped_app_id, incidents, docs, manifests, dependencies)
        hypotheses = self.tools.rank_root_cause_hypotheses(scoped_app_id, [message], [item.model_dump() for item in evidence])
        inconsistency = _detect_inconsistency(docs, manifests)
        likely_causes = _build_likely_causes(hypotheses, evidence, inconsistency)
        next_checks = _build_next_checks(profile, likely_causes, inconsistency)
        missing_data = _missing_data(profile, incidents, docs, manifests)

        if _asks_for_inconsistency(message):
            summary = inconsistency or "I did not find a clear docs-versus-manifest mismatch in the selected evidence."
        elif _asks_for_dependencies(message):
            summary = f"{scoped_app_id} depends on " + ", ".join(sorted({dep.get("name", "unknown") for dep in dependencies})[:6]) + "."
        elif _asks_for_briefing(message):
            summary = f"{scoped_app_id} is a tier {profile.get('tier')} {profile.get('criticality')} service owned by {profile.get('technical_owner')} with {profile.get('incident_count')} ingested incidents."
        else:
            summary = _default_summary(scoped_app_id, likely_causes, incidents, inconsistency)

        response = AgentResponse(
            app_id=scoped_app_id,
            answer=_compose_answer(scoped_app_id, summary, likely_causes, next_checks, missing_data, evidence),
            summary=summary,
            likely_causes=likely_causes,
            recommended_next_checks=next_checks,
            evidence=evidence,
            missing_data=missing_data,
        )
        return self._refine_with_llm(message, response)

    def _build_llm(self) -> ChatOpenAI | None:
        if not self.settings.llm_enabled:
            return None
        return ChatOpenAI(
            model=self.settings.openrouter_model,
            api_key=self.settings.openrouter_api_key,
            base_url=self.settings.openrouter_base_url,
            temperature=0.1,
            default_headers={
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "KB Agent Local POC",
            },
        )

    def _refine_with_llm(self, user_message: str, response: AgentResponse) -> AgentResponse:
        if self.llm is None:
            return response
        prompt = (
            "Rewrite the final answer and summary for an executive troubleshooting demo. "
            "Use only the supplied structured evidence. Do not add new evidence IDs, source refs, or facts. "
            "Keep the selected app_id unchanged. Preserve missing_data honestly. "
            "Return JSON with exactly two string keys: answer and summary.\n\n"
            f"User question: {user_message}\n\n"
            f"Structured payload:\n{response.model_dump_json(indent=2)}"
        )
        try:
            completion = self.llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)])
            content = completion.content if isinstance(completion.content, str) else json.dumps(completion.content)
            parsed = _extract_json_object(content)
            answer = parsed.get("answer")
            summary = parsed.get("summary")
            if isinstance(answer, str) and isinstance(summary, str):
                return response.model_copy(update={"answer": answer, "summary": summary})
        except Exception:
            return response
        return response


def _query_for_message(message: str) -> str:
    lower = message.lower()
    if "latency" in lower:
        return "latency queue database connection"
    if "payment" in lower or "callback" in lower:
        return "payment callback queue"
    if "database" in lower or "db" in lower:
        return "database connection orders-db"
    if "inconsistent" in lower or "disagree" in lower:
        return "orders-db queue manifest architecture"
    return message


def _build_evidence(app_id: str, incidents: list[dict[str, Any]], docs: list[dict[str, Any]], manifests: list[dict[str, Any]], dependencies: list[dict[str, Any]]) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    for incident in incidents[:5]:
        evidence.append(
            EvidenceItem(
                id=f"inc:{incident.get('number')}",
                source_type="incident",
                source_ref=incident.get("source_ref", "data/raw/incidents/servicenow_incidents.csv"),
                snippet=f"{incident.get('number')}: {incident.get('short_description')} - {incident.get('description')}",
            )
        )
    for doc in docs[:4]:
        evidence.append(
            EvidenceItem(
                id=f"doc:{doc.get('chunk_id')}",
                source_type="docs",
                source_ref=f"{doc.get('source_file')}#{doc.get('heading_path')}",
                snippet=_trim(doc.get("text", ""), 360),
            )
        )
    for row in manifests[:2]:
        manifest = row.get("manifest", {})
        resources = row.get("resources", [])
        raw_json = manifest.get("raw_json")
        if isinstance(raw_json, str):
            try:
                raw_json = json.loads(raw_json)
            except json.JSONDecodeError:
                raw_json = {}
        dep_names = [dep.get("name") for dep in (raw_json or {}).get("dependencies", []) if dep.get("name")]
        resource_names = [resource.get("name") for resource in resources if resource.get("name")]
        evidence.append(
            EvidenceItem(
                id=f"manifest:{manifest.get('manifest_id')}",
                source_type="manifest",
                source_ref=manifest.get("source_file", "manifest"),
                snippet=f"Manifest dependencies: {', '.join(dep_names[:8])}. Resources: {', '.join(resource_names[:8])}.",
            )
        )
    if dependencies:
        names = ", ".join(sorted({dependency.get("name", "unknown") for dependency in dependencies})[:10])
        evidence.append(EvidenceItem(id=f"graph:{app_id}:dependencies", source_type="graph", source_ref="Neo4j DEPENDS_ON traversal", snippet=f"{app_id} dependency traversal found: {names}."))
    return _dedupe_evidence(evidence)


def _detect_inconsistency(docs: list[dict[str, Any]], manifests: list[dict[str, Any]]) -> str | None:
    doc_text = " ".join(doc.get("text", "") for doc in docs).lower()
    manifest_text = " ".join(str(row.get("manifest", {}).get("raw_json", "")) for row in manifests).lower()
    mismatches = []
    if "orders-db-primary" in doc_text and "orders-db-replica" in manifest_text:
        mismatches.append("Architecture docs say APP001 uses orders-db-primary, but the deployed manifest points at orders-db-replica.")
    if "checkout-payment-events`" in doc_text or "checkout-payment-events " in doc_text:
        if "checkout-payment-events-v1" in manifest_text:
            mismatches.append("Architecture/runbook references checkout-payment-events, while the manifest configures checkout-payment-events-v1.")
    return " ".join(mismatches) if mismatches else None


def _build_likely_causes(hypotheses: list[dict[str, Any]], evidence: list[EvidenceItem], inconsistency: str | None) -> list[LikelyCause]:
    cause_evidence = [item.id for item in evidence]
    causes = [
        LikelyCause(
            title=item["title"],
            confidence=item.get("confidence", "medium"),
            why=f"Supported by scoped evidence mentioning {', '.join(item.get('signals') or ['related operational signals'])}.",
            supporting_evidence_ids=cause_evidence[:5],
        )
        for item in hypotheses[:4]
    ]
    if inconsistency:
        causes.insert(
            0,
            LikelyCause(
                title="Manifest drift from architecture intent",
                confidence="high",
                why=inconsistency,
                supporting_evidence_ids=[item.id for item in evidence if item.source_type in {"docs", "manifest", "incident"}][:5],
            ),
        )
    return causes[:4]


def _build_next_checks(profile: dict[str, Any], likely_causes: list[LikelyCause], inconsistency: str | None) -> list[NextCheck]:
    owner = profile.get("technical_owner")
    checks = []
    if inconsistency:
        checks.append(NextCheck(action="Compare APP001 deployed environment variables and queue bindings against the architecture runbook, then correct the stale binding or update the documented intent.", owner_hint=owner, source="manifest"))
    for cause in likely_causes:
        title = cause.title.lower()
        if "database" in title:
            checks.append(NextCheck(action="Check orders database active connections, pool saturation, and slow query dashboard for APP001 traffic.", owner_hint="Database Operations", source="incident"))
        elif "queue" in title:
            checks.append(NextCheck(action="Check payment-worker consumer lag, queue name, and consumer group for APP001.", owner_hint=owner, source="manifest"))
        elif "inventory" in title:
            checks.append(NextCheck(action="Check APP002 inventory-api latency and recent incidents before treating APP001 as the only fault domain.", owner_hint="Supply Chain Platform", source="graph"))
        elif "gateway" in title:
            checks.append(NextCheck(action="Compare AcmePay callback delivery status with APP001 payment-worker retry logs.", owner_hint=owner, source="docs"))
    checks.append(NextCheck(action="Keep the incident scoped to APP001 evidence unless new telemetry proves cross-app impact.", owner_hint=owner, source="agent"))
    return _dedupe_checks(checks)[:5]


def _missing_data(profile: dict[str, Any], incidents: list[dict[str, Any]], docs: list[dict[str, Any]], manifests: list[dict[str, Any]]) -> list[str]:
    missing = []
    if not incidents:
        missing.append("No scoped incidents matched the question, so recurrence evidence is limited.")
    if not docs:
        missing.append("No architecture or runbook chunks matched the question.")
    if not manifests:
        missing.append("No manifest was ingested for the selected app/environment.")
    if not profile.get("resources"):
        missing.append("No parsed infrastructure resources are linked to the selected app.")
    return missing


def _compose_answer(app_id: str, summary: str, likely_causes: list[LikelyCause], next_checks: list[NextCheck], missing_data: list[str], evidence: list[EvidenceItem]) -> str:
    facts = f"Facts for {app_id}: {summary}"
    hypotheses = "Likely causes: " + "; ".join(f"{cause.title} ({cause.confidence})" for cause in likely_causes) + "."
    checks = "Next checks: " + "; ".join(check.action for check in next_checks[:3]) + "."
    citations = "Evidence: " + ", ".join(item.id for item in evidence[:6]) + "."
    missing = f"Missing data: {'; '.join(missing_data)}" if missing_data else "Missing data: none obvious in the ingested POC dataset."
    return "\n\n".join([facts, hypotheses, checks, citations, missing])


def _default_summary(app_id: str, likely_causes: list[LikelyCause], incidents: list[dict[str, Any]], inconsistency: str | None) -> str:
    incident_numbers = ", ".join(incident.get("number", "") for incident in incidents[:4])
    top_cause = likely_causes[0].title if likely_causes else "insufficient evidence"
    base = f"The strongest scoped hypothesis for {app_id} is {top_cause}."
    if incident_numbers:
        base += f" Recent supporting incidents include {incident_numbers}."
    if inconsistency:
        base += f" {inconsistency}"
    return base


def _asks_for_inconsistency(message: str) -> bool:
    lower = message.lower()
    return any(term in lower for term in ["inconsistent", "disagree", "agree", "mismatch", "compare"])


def _asks_for_dependencies(message: str) -> bool:
    lower = message.lower()
    return "depend" in lower or "impact" in lower or "upstream" in lower or "downstream" in lower


def _asks_for_briefing(message: str) -> bool:
    return "briefing" in message.lower() or "executive" in message.lower()


def _trim(text: str, limit: int) -> str:
    normalized = " ".join(text.split())
    return normalized if len(normalized) <= limit else normalized[: limit - 3] + "..."


def _dedupe_evidence(items: list[EvidenceItem]) -> list[EvidenceItem]:
    seen = set()
    result = []
    for item in items:
        if item.id in seen:
            continue
        seen.add(item.id)
        result.append(item)
    return result


def _dedupe_checks(items: list[NextCheck]) -> list[NextCheck]:
    seen = set()
    result = []
    for item in items:
        if item.action in seen:
            continue
        seen.add(item.action)
        result.append(item)
    return result


def _extract_json_object(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        stripped = stripped.removeprefix("json").strip()
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {}
        value = json.loads(stripped[start : end + 1])
    return value if isinstance(value, dict) else {}
