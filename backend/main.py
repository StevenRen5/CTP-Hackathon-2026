"""Building Report Card — address-extraction backend.

Endpoints:
  GET  /health   sanity check
  POST /extract  listing page text + URL -> structured NYC address
"""

from dotenv import load_dotenv

load_dotenv()  # read backend/.env before importing anything that needs the key

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from gemini import extract_address

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
def extract(body: PageIn):
    """Raw listing page text + URL -> clean structured address."""
    if not body.page_text.strip() and not body.page_url.strip():
        raise HTTPException(status_code=400, detail="page_text and page_url are both empty")
    try:
        return extract_address(body.page_text, body.page_url)
    except RuntimeError as e:
        # e.g. missing API key — surface it clearly instead of a 500 stacktrace.
        raise HTTPException(status_code=500, detail=str(e))
