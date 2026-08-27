import json
import os
from datetime import date
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel


MODEL = "gemini-3.5-flash-lite"
DIRECTORY = Path(__file__).parent


class CategoryExplanations(BaseModel):
    safety: str
    building_conditions: str
    pests: str
    responsiveness: str
    trend: str


class GeminiEvaluation(BaseModel):
    headline: str
    summary: str
    category_explanations: CategoryExplanations
    prospects: Literal["improving", "stable", "worsening", "n/a"]
    caveats: list[str]


PROMPT = """You explain a deterministic NYC building report card to a renter.

Rules:
- The supplied scores are final. Never recalculate or change them.
- Use only the supplied facts.
- Do not invent complaints, violations, dates, or causes.
- A complaint is a report, not a confirmed condition.
- Do not call the building safe, unsafe, habitable, or uninhabitable.
- Confidence describes data completeness, not building quality.
- Explain each category in one short sentence.
- Keep the summary to at most two short sentences.
- Prospects must match the supplied trend direction.
- Include a caveat that the assessment uses available public records.
- Return only JSON matching the required schema.

Evaluation:
{context}
"""


def parse_date(value: object) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def is_recent(item: dict, today: date, months: int = 12) -> bool:
    reported = parse_date(item.get("date_reported"))
    return bool(reported and 0 <= (today - reported).days <= months * 31)


def category_facts(items: list[dict], today: date) -> dict[str, list[str]]:
    """Aggregate facts locally so Gemini never receives raw records."""

    recent = [item for item in items if is_recent(item, today)]
    facts = {name: [] for name in (
        "safety", "building_conditions", "pests", "responsiveness", "trend"
    )}

    for category in ("safety", "building_conditions"):
        hpd = [item for item in recent if item.get("source") == "hpd"
               and item.get("classification") == category]
        for severity in ("C", "B", "A"):
            count = sum(item.get("severity") == severity
                        and not item.get("date_resolved") for item in hpd)
            if count:
                facts[category].append(
                    f"{count} recent open HPD Class {severity} violation"
                    + ("s" if count != 1 else "")
                )

        complaints = sum(item.get("source") == "311"
                         and item.get("classification") == category for item in recent)
        if complaints:
            facts[category].append(
                f"{complaints} recent 311 report" + ("s" if complaints != 1 else "")
            )

    failed_rodent = sum(item.get("source") == "rodent"
                        and "rat activity" in str(item.get("description") or "").lower()
                        for item in recent)
    bait = sum(item.get("source") == "rodent"
               and "bait applied" in str(item.get("description") or "").lower()
               for item in recent)
    if failed_rodent:
        facts["pests"].append(
            f"{failed_rodent} recent failed rat-activity inspection"
            + ("s" if failed_rodent != 1 else "")
        )
    if bait:
        facts["pests"].append(
            f"{bait} recent bait treatment" + ("s" if bait != 1 else "")
        )

    actionable = [item for item in recent
                  if item.get("source") in {"311", "hpd"}
                  and item.get("classification") in {
                      "safety", "building_conditions", "pest"
                  }]
    unresolved = sum(not item.get("date_resolved") for item in actionable)
    overdue = sum(
        not item.get("date_resolved")
        and (due := parse_date(item.get("date_expected_resolve"))) is not None
        and due < today
        for item in actionable
    )
    if actionable:
        facts["responsiveness"].append(
            f"{len(actionable) - unresolved} of {len(actionable)} recent actionable records were resolved"
        )
    if overdue:
        verb = "were" if overdue != 1 else "was"
        facts["responsiveness"].append(
            f"{overdue} unresolved violation{'s' if overdue != 1 else ''} {verb} "
            "past the listed correction date"
        )
    return facts


def limitations(records: dict) -> list[str]:
    source_keys = {"311": "c311", "hpd": "hpd", "dob": "dob", "rodent": "rodent"}
    returned = {key: 0 for key in source_keys.values()}
    for item in records.get("items") or []:
        key = source_keys.get(str(item.get("source", "")).lower())
        if key:
            returned[key] += 1
    totals = records.get("counts") or {}
    capped = [key for key, amount in returned.items() if int(totals.get(key, 0)) > amount]
    return (["Only the most recent returned records were analyzed for: "
             + ", ".join(capped) + "."] if capped else [])


def build_context(evaluation: dict, records: dict, today: date | None = None) -> dict:
    """Build the compact context packet sent to Gemini."""

    facts = category_facts(records.get("items") or [], today or date.today())
    return {
        "overall": {
            "score": evaluation["score"],
            "grade": evaluation["grade"],
            "confidence": evaluation["confidence"],
        },
        "categories": {
            name: {**value, "facts": facts[name]}
            for name, value in evaluation["categories"].items()
        },
        "limitations": limitations(records),
    }


def explain_evaluation(evaluation: dict, records: dict) -> dict:
    """Make exactly one Gemini request and never retry automatically."""

    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set.")

    context = build_context(evaluation, records)
    client = genai.Client(api_key=key)
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=PROMPT.format(context=json.dumps(context, separators=(",", ":"))),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=GeminiEvaluation,
                temperature=0,
                max_output_tokens=800,
            ),
        )
    finally:
        client.close()
    if response.parsed is not None:
        return response.parsed.model_dump()
    if response.text:
        return GeminiEvaluation.model_validate_json(response.text).model_dump()

    reason = response.candidates[0].finish_reason if response.candidates else "unknown"
    raise RuntimeError(f"Gemini returned no usable output (finish reason: {reason}).")


def main(
    records_json: str | Path = "live_records20.json",
    eval_json: str | Path = "eval.json",
    output_json: str | Path = "gemini.json"
) -> None:
    load_dotenv()
    eval_path = DIRECTORY / eval_json
    output_path = DIRECTORY / output_json
    records_path = DIRECTORY / records_json

    evaluation = json.loads(eval_path.read_text(encoding="utf-8"))
    records = json.loads(records_path.read_text(encoding="utf-8"))
    explanation = explain_evaluation(evaluation, records)
    output_path.write_text(json.dumps(explanation, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
