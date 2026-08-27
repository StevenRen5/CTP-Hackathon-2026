"""Gemini-powered address extraction.

Turns the raw, messy text of a listing page into one clean, structured NYC
address. This is the 'scrape' step done by an LLM instead of a DOM parser, so
Zillow layout changes don't break it.
"""

import os
from google import genai
from google.genai import types
from pydantic import BaseModel

MODEL = "gemini-3.6-flash"

# Lazily built so importing this module never requires a key (e.g. for /health).
_client = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError(
                "GEMINI_API_KEY not set. Add it to backend/.env "
                "(see .env.example)."
            )
        _client = genai.Client(api_key=key)
    return _client


class ExtractedAddress(BaseModel):
    """Structured result Gemini must return. All fields required so the model
    always fills them; empty strings + found=False when nothing is present."""

    found: bool
    full_address: str  # e.g. "123 Main St, Brooklyn, NY 11201"
    street: str  # e.g. "123 Main St"
    city: str  # e.g. "Brooklyn"
    borough: str  # Manhattan | Brooklyn | Queens | Bronx | Staten Island | ""
    state: str  # e.g. "NY"
    zip: str  # e.g. "11201"


_PROMPT = """You are extracting the single primary property address for a \
real-estate listing (Zillow or StreetEasy).

MOST RELIABLE SOURCE — the page URL. Zillow encodes the full address in the \
/homedetails/ slug, e.g.
  .../homedetails/2155-82nd-St-APT-3N-Brooklyn-NY-11214/245061078_zpid/
means 2155 82nd St, Brooklyn, NY 11214. If the URL contains such a slug, trust \
it over the page text — the text often belongs to a search-results list behind \
a popup, not the property being viewed.

Fall back to the page text only if the URL has no usable address.

Rules:
- If the property is in New York City, fill `borough` with one of: Manhattan, \
Brooklyn, Queens, Bronx, Staten Island. Otherwise leave `borough` empty.
- Do not include the apartment/unit number in `street` (e.g. "2155 82nd St", \
not "2155 82nd St Apt 3N") — building-level datasets key off the building.
- If you cannot confidently find the property address, set found=false and \
leave the string fields empty.

Page URL:
{page_url}

Listing page text:
---
{page_text}
---"""


def extract_address(page_text: str, page_url: str = "") -> ExtractedAddress:
    """Extract the primary listing address.

    The page URL is the primary signal (Zillow puts the address in the
    /homedetails/ slug); page_text is a fallback for pages without it.
    """
    client = _get_client()
    prompt = _PROMPT.format(
        page_url=page_url or "(none provided)",
        page_text=page_text[:20000],
    )

    resp = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ExtractedAddress,
            temperature=0,  # deterministic — we want the same address every time
        ),
    )

    # With a pydantic response_schema, google-genai parses the JSON for us.
    result = resp.parsed
    if result is None:
        # Fallback if parsing failed for some reason.
        raise RuntimeError(f"Gemini returned unparseable output: {resp.text!r}")

    print("\n[extract] ---------------------------------------------")
    print(f"[extract] url    : {page_url or '(none)'}")
    print(f"[extract] found  : {result.found}")
    print(f"[extract] address: {result.full_address!r}")
    print(f"[extract] borough: {result.borough!r}  state: {result.state!r}")
    print("[extract] ---------------------------------------------\n")

    return result
