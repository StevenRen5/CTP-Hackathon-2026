"""Building Report Card — backend.

Endpoints:
  GET  /health   sanity check
  POST /extract  listing page text + URL -> structured NYC address
  POST /records  address -> that building's records from 4 NYC datasets
  POST /report   listing page -> full graded report card
                 (extract -> records -> deterministic score -> Gemini explanation)
"""

from dotenv import load_dotenv

load_dotenv()  # read backend/.env before importing anything that needs the key

import asyncio

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from eval import evaluate_property
from gemini import answer_question, extract_address
from gemini_eval import explain_evaluation
from nyc import fetch_building_records

app = FastAPI(title="Address Extraction API")

# Wide-open CORS so the Chrome extension (a chrome-extension:// origin) can call
# us during the hackathon. Tighten before anything real.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class PageIn(BaseModel):
    page_text: str
    page_url: str = ""  # Zillow /homedetails/ slug is the most reliable source


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/extract")
async def extract(body: PageIn):
    """Raw listing page text + URL -> clean structured address."""
    if not body.page_text.strip() and not body.page_url.strip():
        raise HTTPException(status_code=400, detail="page_text and page_url are both empty")
    try:
        return await extract_address(body.page_text, body.page_url)
    except RuntimeError as e:
        # e.g. missing API key — surface it clearly instead of a 500 stacktrace.
        raise HTTPException(status_code=500, detail=str(e))


class RecordsIn(BaseModel):
    address: str
    limit: int = 100  # max records per dataset


@app.post("/records")
async def records(body: RecordsIn):
    """Address -> that building's records from all four NYC datasets.

    Resolves the address to a building (BBL + BIN) via NYC GeoSearch, then pulls
    311, HPD, DOB, and Rodent records for it. Returns per-dataset counts +
    capped record samples (see `limit`). `resolved: false` means the address
    couldn't be matched to an NYC building.
    """
    if not body.address.strip():
        raise HTTPException(status_code=400, detail="address is empty")
    try:
        return await fetch_building_records(body.address, body.limit)
    except httpx.HTTPError as e:
        # GeoSearch or Socrata unreachable / erroring.
        raise HTTPException(status_code=502, detail=f"Upstream NYC data error: {e}")


def _merge_categories(evaluation: dict, explanation: dict) -> dict:
    """Combine the deterministic category scores with Gemini's per-category
    explanations into one object the frontend can render."""
    explanations = explanation.get("category_explanations", {})
    merged = {}
    for name, value in evaluation["categories"].items():
        merged[name] = {**value, "explanation": explanations.get(name, "")}
    return merged


@app.post("/report")
async def report(body: PageIn):
    """The full pipeline in one call: listing page -> graded report card.

    extract address -> fetch NYC records -> deterministic score (eval.py) ->
    Gemini explanation (gemini_eval.py). Gemini never recomputes the score.
    """
    if not body.page_text.strip() and not body.page_url.strip():
        raise HTTPException(status_code=400, detail="page_text and page_url are both empty")

    try:
        addr = await extract_address(body.page_text, body.page_url)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not addr.found or not addr.full_address:
        raise HTTPException(status_code=422, detail="Couldn't find a property address on this page.")

    # NYC-only guard: GeoSearch mis-resolves non-NYC addresses to a random NYC
    # building, so refuse anything outside the five boroughs.
    if (addr.state and addr.state.upper() != "NY") or not addr.borough:
        raise HTTPException(status_code=422, detail="This tool only covers NYC buildings.")

    # Prefer street + borough for a clean geocode (no unit number).
    lookup = f"{addr.street}, {addr.borough}" if addr.street else addr.full_address
    try:
        records = await fetch_building_records(lookup, limit=40)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Upstream NYC data error: {e}")

    if not records["resolved"]:
        raise HTTPException(status_code=404, detail=f"Couldn't match {addr.full_address} to an NYC building.")

    # Deterministic score (fast, pure Python), then Gemini explanation. The
    # explanation call is sync (it opens its own client), so run it off the
    # event loop to avoid the FastAPI threadpool hang.
    evaluation = evaluate_property(records)
    try:
        explanation = await asyncio.to_thread(explain_evaluation, evaluation, records)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    building = records["building"]
    return {
        "address": addr.full_address,
        "bbl": building.get("bbl", ""),
        "units": building.get("units"),
        "grade": evaluation["grade"],
        "score": evaluation["score"],
        "confidence": evaluation["confidence"],
        "headline": explanation.get("headline", ""),
        "summary": explanation.get("summary", ""),
        "prospects": explanation.get("prospects", "n/a"),
        "caveats": explanation.get("caveats", []),
        "categories": _merge_categories(evaluation, explanation),
        "counts": records["counts"],
    }


class ChatIn(BaseModel):
    address: str
    question: str


@app.post("/chat")
async def chat(body: ChatIn):
    """Answer a freeform question grounded in the building's NYC records."""
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="question is empty")
    if not body.address.strip():
        raise HTTPException(status_code=400, detail="address is empty")

    try:
        records = await fetch_building_records(body.address, limit=40)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Upstream NYC data error: {e}")

    if not records["resolved"]:
        raise HTTPException(status_code=404, detail="Couldn't match that address to an NYC building.")

    try:
        answer = await answer_question(
            records["building"], records["counts"], records["items"], body.question
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"answer": answer}
