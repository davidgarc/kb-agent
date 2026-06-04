import csv
from pathlib import Path

from kb_agent.ingestion.normalizers import NormalizedIncident


def load_incidents(path: Path) -> list[NormalizedIncident]:
    incidents: list[NormalizedIncident] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            number = row["number"].strip()
            app_id = row.get("app_id", "").strip().upper()
            incidents.append(
                NormalizedIncident(
                    incident_id=f"incident-{number}",
                    number=number,
                    app_id=app_id,
                    opened_at=row.get("opened_at", "").strip(),
                    closed_at=row.get("closed_at", "").strip() or None,
                    priority=row.get("priority", "").strip(),
                    severity=row.get("severity", "").strip(),
                    state=row.get("state", "").strip(),
                    short_description=row.get("short_description", "").strip(),
                    description=row.get("description", "").strip(),
                    resolution_notes=row.get("resolution_notes", "").strip() or None,
                    assignment_group=row.get("assignment_group", "").strip() or None,
                    ci_name=row.get("cmdb_ci", "").strip() or None,
                    raw=dict(row),
                    source_ref=str(path),
                )
            )
    return incidents

