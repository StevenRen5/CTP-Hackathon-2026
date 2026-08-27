"""Building Report Card — backend.

Endpoints:
  GET  /health   sanity check
  POST /extract  listing page text + URL -> structured NYC address
  POST /records  address -> that building's records from 4 NYC datasets
"""

from dotenv import load_dotenv

load_dotenv()  # read backend/.env before importing anything that needs the key

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from gemini import extract_address
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
