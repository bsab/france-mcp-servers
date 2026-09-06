"""Ready score, rubric v1: documented readiness, not runtime reliability."""

from __future__ import annotations

RUBRIC_VERSION = 1
CRITERIA = {
    "installation": ("Installation or access", 30),
    "configuration": ("Configuration and prerequisites", 20),
    "tools": ("Capabilities and examples", 20),
    "compatibility": ("Transport and compatible clients", 15),
    "license": ("Explicit license", 10),
    "limitations": ("Known limitations", 5),
}
STATUS_LABELS = {
    "absent": "Not documented",
    "partial": "Partial",
    "complete": "Complete",
}
STATUS_FACTORS = {"absent": 0, "partial": 0.5, "complete": 1}


def readiness_score(server: dict) -> float | None:
    assessment = server.get("quality")
    if not assessment or assessment["status"] == "unassessed":
        return None
    if assessment["rubric_version"] != RUBRIC_VERSION:
        raise ValueError("Unsupported rubric version")
    return sum(
        weight * STATUS_FACTORS[assessment["criteria"][key]["status"]]
        for key, (_, weight) in CRITERIA.items()
    )


def readiness_label(server: dict) -> str:
    score = readiness_score(server)
    return "Unassessed" if score is None else f"{score:g}/100"


def quality_rubric() -> dict:
    return {
        "version": RUBRIC_VERSION,
        "name": "Ready score",
        "criteria": [
            {"id": key, "label": label, "weight": weight}
            for key, (label, weight) in CRITERIA.items()
        ],
        "statuses": {
            key: {"label": STATUS_LABELS[key], "factor": factor}
            for key, factor in STATUS_FACTORS.items()
        },
    }
