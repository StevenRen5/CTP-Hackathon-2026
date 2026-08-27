"""Calculate the frontend report-card scores from the response produced by nyc.py."""

from __future__ import annotations

import json
from datetime import date
from math import log2
from pathlib import Path
from typing import Any


CATEGORY_MAX = {
    "safety": 35,
    "building_conditions": 25,
    "pest": 15,
}

CATEGORY_THRESHOLD = {
    "safety": 15,
    "building_conditions": 20,
    "pest": 12,
}

SOURCE_WEIGHT = {
    "311": 0.35,
    "hpd": 1.0,
    "rodent": 0.75,
    "dob": 0.30,
}

HPD_SEVERITY = {"A": 1, "B": 7, "C": 12}
MINIMUM_UNITS = 5


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def months_old(item: dict, today: date) -> float | None:
    reported = parse_date(item.get("date_reported"))
    return None if reported is None else max(0, (today - reported).days / 30.4375)


def recency_weight(item: dict, today: date) -> float:
    age = months_old(item, today)
    if age is None or age > 24:
        return 0.10
    if age > 12:
        return 0.35
    if age > 6:
        return 0.70
    return 1.0


def severity_weight(item: dict) -> float:
    source = str(item.get("source", "")).lower()
    category = str(item.get("classification", "")).lower()
    severity = str(item.get("severity") or "").upper()
    description = str(item.get("description") or "").lower()

    if source == "hpd":
        if severity in HPD_SEVERITY:
            return HPD_SEVERITY[severity]
        if severity == "I":
            return 12 if category == "safety" else 1
    if source == "311":
        return 3 if category == "safety" else 1.5
    if source == "rodent":
        if "bait applied" in description:
            return 0.25
        return 3 if "failed" in description or "activity" in description else 1
    if source == "dob":
        return 1.5
    return 1


def is_scorable(item: dict) -> bool:
    if item_category(item) not in CATEGORY_MAX:
        return False
    if str(item.get("source", "")).lower() != "rodent":
        return True
    description = str(item.get("description") or "").lower()
    return "passed" not in description and "no activity" not in description


def item_category(item: dict) -> str:
    """Return the scoring category, excluding administrative non-condition records."""

    description = str(item.get("description") or "").upper()
    if "FILE ANNUAL BEDBUG REPORT" in description:
        return "other"
    return str(item.get("classification", "")).lower()


def status_weight(item: dict, today: date) -> float:
    if str(item.get("source", "")).lower() == "dob":
        expiration = parse_date(item.get("date_expected_resolve"))
        return 1.0 if expiration is None or expiration >= today else 0.20
    return 0.35 if parse_date(item.get("date_resolved")) else 1.0


def item_penalty(
    item: dict,
    today: date,
    *,
    include_status: bool = True,
    include_recency: bool = True,
) -> float:
    if not is_scorable(item):
        return 0
    source = str(item.get("source", "")).lower()
    penalty = severity_weight(item) * SOURCE_WEIGHT.get(source, 0.25)
    if include_status:
        penalty *= status_weight(item, today)
    if include_recency:
        penalty *= recency_weight(item, today)
    return penalty


def effective_units(units: Any) -> int:
    try:
        return max(int(units), MINIMUM_UNITS)
    except (TypeError, ValueError):
        return MINIMUM_UNITS


def category_score(items: list[dict], category: str, units: int, today: date) -> int:
    penalty = sum(
        item_penalty(item, today)
        for item in items
        if item_category(item) == category
    )
    penalty_per_10_units = penalty / units * 10
    maximum = CATEGORY_MAX[category]
    score = maximum / (1 + penalty_per_10_units / CATEGORY_THRESHOLD[category])
    return round(max(0, min(score, maximum)))


def responsiveness_score(items: list[dict], today: date) -> int:
    relevant = [
        item
        for item in items
        if is_scorable(item)
        and str(item.get("source", "")).lower() in {"311", "hpd"}
        and months_old(item, today) is not None
        and months_old(item, today) <= 24
    ]
    if not relevant:
        return 15

    resolved = [item for item in relevant if parse_date(item.get("date_resolved"))]
    due = [item for item in relevant if parse_date(item.get("date_expected_resolve"))]
    resolved_with_due = [item for item in resolved if parse_date(item.get("date_expected_resolve"))]

    closed_rate = len(resolved) / len(relevant)
    on_time_rate = (
        sum(
            parse_date(item["date_resolved"]) <= parse_date(item["date_expected_resolve"])
            for item in resolved_with_due
        ) / len(resolved_with_due)
        if resolved_with_due else 0.5
    )
    overdue_rate = (
        sum(
            not parse_date(item.get("date_resolved"))
            and parse_date(item.get("date_expected_resolve")) < today
            for item in due
        ) / len(due)
        if due else 0.5
    )

    score = 15 * (0.4 * closed_rate + 0.4 * on_time_rate + 0.2 * (1 - overdue_rate))
    return round(score)


def trend_score(items: list[dict], units: int, today: date) -> tuple[int, str]:
    recent_items = [
        item
        for item in items
        if is_scorable(item)
        and months_old(item, today) is not None
        and months_old(item, today) <= 12
    ]
    if not recent_items:
        return 10, "stable"
    if len(recent_items) < 3:
        return 5, "n/a"

    last_six = [item for item in recent_items if months_old(item, today) <= 6]
    prior_six = [item for item in recent_items if months_old(item, today) > 6]
    last_rate = sum(
        item_penalty(item, today, include_status=False, include_recency=False)
        for item in last_six
    ) / units
    prior_rate = sum(
        item_penalty(item, today, include_status=False, include_recency=False)
        for item in prior_six
    ) / units

    ratio = (last_rate + 1) / (prior_rate + 1)
    score = round(max(0, min(5 - 5 * log2(ratio), 10)))
    direction = "improving" if ratio <= 0.75 else "worsening" if ratio >= 1.25 else "stable"
    return score, direction


def confidence(payload: dict) -> str:
    building = payload.get("building") or {}
    counts = payload.get("counts") or {}
    if not building.get("units"):
        return "low"
    source_keys = {"311": "c311", "hpd": "hpd", "dob": "dob", "rodent": "rodent"}
    returned = {key: 0 for key in source_keys.values()}
    for item in payload.get("items") or []:
        key = source_keys.get(str(item.get("source", "")).lower())
        if key:
            returned[key] += 1
    if any(int(counts.get(key, 0)) > returned[key] for key in returned):
        return "medium"
    if all(key in counts for key in source_keys.values()):
        return "high"
    return "medium"


def grade(score: int) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def evaluate_property(payload: dict, today: date | None = None) -> dict:
    """Return the small evaluation object consumed by the frontend."""

    if not payload.get("resolved") or not payload.get("building"):
        return {"error": "Building data could not be resolved."}

    current_date = today or date.today()
    building = payload["building"]
    items = payload.get("items") or []
    units = effective_units(building.get("units"))

    safety = category_score(items, "safety", units, current_date)
    conditions = category_score(items, "building_conditions", units, current_date)
    pests = category_score(items, "pest", units, current_date)
    responsiveness = responsiveness_score(items, current_date)
    trend, direction = trend_score(items, units, current_date)
    total = safety + conditions + pests + responsiveness + trend

    return {
        "score": total,
        "grade": grade(total),
        "confidence": confidence(payload),
        "categories": {
            "safety": {"score": safety, "max": 35},
            "building_conditions": {"score": conditions, "max": 25},
            "pests": {"score": pests, "max": 15},
            "responsiveness": {"score": responsiveness, "max": 15},
            "trend": {"score": trend, "max": 10, "direction": direction},
        },
    }


def write_evaluation(payload: dict, output_path: Path | str = "eval.json") -> dict:
    result = evaluate_property(payload)
    Path(output_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    directory = Path(__file__).parent
    payload = json.loads((directory / "live_records20.json").read_text(encoding="utf-8"))
    write_evaluation(payload, directory / "eval.json")


if __name__ == "__main__":
    main()
