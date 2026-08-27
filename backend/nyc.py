"""NYC Open Data fetchers + normalization.

Given a street address, resolve it to a building (BBL + BIN via NYC GeoSearch),
then pull that building's records from four datasets and normalize them into a
single classified schema:

  311 Service Requests        erm2-nwe9   filter: bbl
  HPD Violations              wvxf-dwi5   filter: boroid + block + lot (strings)
  DOB Permit Issuance         ipu4-2q9a   filter: bin__
  DOHMH Rodent Inspection     p937-wjvj   filter: boro_code + block + lot (strings)

Unit count comes from a fifth dataset, PLUTO (64uk-42ks), keyed by bbl.

BBL (Borough-Block-Lot) is the shared key. "3017640001" = borough 3, block
1764, lot 1 — block/lot in HPD and Rodent are strings with leading zeros stripped.

Each record is normalized to:
  { source, address, classification, severity, description,
    date_reported, date_resolved, date_expected_resolve }

  classification: "safety" | "building_conditions" | "pest" | "other"
  severity:       "A" | "B" | "C" (HPD only) | null
"""

import asyncio
import os

import httpx

GEOSEARCH_URL = "https://geosearch.planninglabs.nyc/v2/search"
SOCRATA = "https://data.cityofnewyork.us/resource"

DATASET = {
    "c311": "erm2-nwe9",
    "hpd": "wvxf-dwi5",
    "dob": "ipu4-2q9a",
    "rodent": "p937-wjvj",
    "pluto": "64uk-42ks",
}


def _socrata_headers() -> dict:
    # An app token is optional but lifts rate limits. Set SOCRATA_APP_TOKEN in .env.
    token = os.environ.get("SOCRATA_APP_TOKEN")
    return {"X-App-Token": token} if token else {}


def parse_bbl(bbl: str) -> tuple[str, str, str]:
    """'3017640001' -> ('3', '1764', '1'). Strips leading zeros from block/lot
    to match how HPD and Rodent store them."""
    return bbl[0], str(int(bbl[1:6])), str(int(bbl[6:10]))


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def _norm_date(value: str | None) -> str | None:
    """Normalize a date to 'YYYY-MM-DD'. Handles ISO timestamps
    ('2026-06-05T00:00:00.000') and DOB's 'MM/DD/YYYY'. None -> None."""
    if not value:
        return None
    value = value.strip()
    if "/" in value:  # MM/DD/YYYY
        parts = value.split("/")
        if len(parts) == 3:
            m, d, y = parts
            return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
        return value
    return value[:10]  # ISO -> date portion


def _join(*parts: str | None, sep: str = " — ") -> str:
    return sep.join(p.strip() for p in parts if p and p.strip())


def _classify_311(complaint_type: str | None) -> str:
    t = (complaint_type or "").lower()
    if any(k in t for k in ("rodent", "pest", "mosquito", "unsanitary animal")):
        return "pest"
    if any(k in t for k in ("fire", "safety", "gas", "electric", "elevator", "structural", "emergency", "asbestos")):
        return "safety"
    if any(k in t for k in ("heat", "hot water", "plumbing", "paint", "plaster", "water leak",
                            "door", "window", "general", "dirty", "sanitation", "sewer",
                            "appliance", "mold", "ceiling", "floor", "wall")):
        return "building_conditions"
    return "other"


def _classify_hpd(description: str | None) -> str:
    d = (description or "").upper()
    if any(k in d for k in ("ROACH", "MICE", "MOUSE", "RODENT", "VERMIN", "BEDBUG", "BED BUG", "INSECT", "PEST")):
        return "pest"
    if any(k in d for k in ("FIRE", "CARBON MONOXIDE", "SMOKE DETECT", "GAS", "LEAD", "EGRESS", "SELF-CLOSING", "SELF CLOSING", "ELECTRIC")):
        return "safety"
    return "building_conditions"


def _item_311(r: dict, building_addr: str) -> dict:
    return {
        "source": "311",
        "address": r.get("incident_address") or building_addr,
        "classification": _classify_311(r.get("complaint_type")),
        "severity": None,
        "description": _join(r.get("complaint_type"), r.get("descriptor"), sep=": "),
        "date_reported": _norm_date(r.get("created_date")),
        "date_resolved": _norm_date(r.get("closed_date")) if r.get("status") == "Closed" else None,
        "date_expected_resolve": None,  # 311 has no correct-by date
    }


def _item_hpd(r: dict, building_addr: str) -> dict:
    addr = _join(r.get("housenumber"), r.get("streetname"), sep=" ") or building_addr
    closed = (r.get("violationstatus") or "").lower() == "close"
    return {
        "source": "hpd",
        "address": addr,
        "classification": _classify_hpd(r.get("novdescription")),
        "severity": (r.get("class") or "").upper() or None,
        "description": r.get("novdescription"),
        "date_reported": _norm_date(r.get("novissueddate") or r.get("inspectiondate")),
        "date_resolved": _norm_date(r.get("currentstatusdate")) if closed else None,
        "date_expected_resolve": _norm_date(r.get("originalcorrectbydate")),
    }


def _item_dob(r: dict, building_addr: str) -> dict:
    addr = _join(r.get("house__"), r.get("street_name"), sep=" ") or building_addr
    return {
        "source": "dob",
        "address": addr,
        "classification": "building_conditions",  # permits = construction/renovation
        "severity": None,
        "description": _join(
            f"{r.get('permit_type', '')} permit".strip(),
            r.get("job_type"),
            r.get("work_type"),
            r.get("permit_status"),
        ),
        "date_reported": _norm_date(r.get("filing_date")),
        "date_resolved": _norm_date(r.get("issuance_date")),  # issued = the permit's "done"
        "date_expected_resolve": _norm_date(r.get("expiration_date")),
    }


def _item_rodent(r: dict, building_addr: str) -> dict:
    result = r.get("result") or ""
    # A passed/no-activity inspection is effectively "resolved" on its date.
    resolved = r.get("inspection_date") if ("passed" in result.lower() or "no activity" in result.lower()) else None
    return {
        "source": "rodent",
        "address": building_addr,  # rodent dataset carries no street address
        "classification": "pest",
        "severity": None,
        "description": _join(r.get("inspection_type"), result, sep=": "),
        "date_reported": _norm_date(r.get("inspection_date")),
        "date_resolved": _norm_date(resolved),
        "date_expected_resolve": None,
    }


# ---------------------------------------------------------------------------
# API calls
# ---------------------------------------------------------------------------

async def geosearch(address: str, client: httpx.AsyncClient) -> dict | None:
    """Resolve a free-text address to a building. Returns bbl/bin/label, or None.
    GeoSearch occasionally 503s; retry a couple of times before giving up."""
    for attempt in range(3):
        try:
            r = await client.get(GEOSEARCH_URL, params={"text": address, "size": 1})
            r.raise_for_status()
            features = r.json().get("features", [])
            if not features:
                return None
            props = features[0]["properties"]
            pad = props.get("addendum", {}).get("pad", {})
            if not pad.get("bbl"):
                return None
            return {"bbl": pad.get("bbl"), "bin": pad.get("bin"), "label": props.get("label")}
        except (httpx.HTTPStatusError, httpx.TransportError):
            if attempt == 2:
                raise
            await asyncio.sleep(0.6)
    return None


async def fetch_units(client: httpx.AsyncClient, bbl: str) -> int | None:
    """Unit count for a building from PLUTO. Prefers total units, falls back to
    residential units. Returns None if the lot isn't in PLUTO."""
    r = await client.get(
        f"{SOCRATA}/{DATASET['pluto']}.json",
        params={"bbl": bbl, "$select": "unitstotal,unitsres", "$limit": 1},
        headers=_socrata_headers(),
    )
    r.raise_for_status()
    rows = r.json()
    if not rows:
        return None
    raw = rows[0].get("unitstotal") or rows[0].get("unitsres")
    try:
        return int(float(raw)) if raw is not None else None
    except (TypeError, ValueError):
        return None


async def _query(client, dataset_id, where, select, order, count_col, limit) -> dict:
    """Run a records query and a count query for one dataset, concurrently.
    Returns {"count": int, "records": [...]}."""
    base = f"{SOCRATA}/{dataset_id}.json"
    headers = _socrata_headers()
    records_res, count_res = await asyncio.gather(
        client.get(base, params={"$where": where, "$select": select, "$order": order, "$limit": limit}, headers=headers),
        client.get(base, params={"$where": where, "$select": f"count({count_col})"}, headers=headers),
    )
    records_res.raise_for_status()
    count_res.raise_for_status()
    count_rows = count_res.json()
    count = int(count_rows[0][f"count_{count_col}"]) if count_rows else 0
    return {"count": count, "records": records_res.json()}


async def fetch_311(client, bbl, limit):
    return await _query(
        client, DATASET["c311"],
        where=f"bbl='{bbl}'",
        select="created_date,closed_date,status,complaint_type,descriptor,incident_address",
        order="created_date DESC", count_col="unique_key", limit=limit,
    )


async def fetch_hpd(client, boro, block, lot, limit):
    return await _query(
        client, DATASET["hpd"],
        where=f"boroid='{boro}' AND block='{block}' AND lot='{lot}'",
        select="novissueddate,inspectiondate,class,novdescription,violationstatus,"
               "currentstatusdate,originalcorrectbydate,housenumber,streetname",
        order="novissueddate DESC", count_col="violationid", limit=limit,
    )


async def fetch_dob(client, bin_, limit):
    return await _query(
        client, DATASET["dob"],
        where=f"bin__='{bin_}'",
        select="filing_date,issuance_date,expiration_date,job_type,permit_type,"
               "permit_subtype,permit_status,work_type,house__,street_name",
        order="issuance_date DESC", count_col="job__", limit=limit,
    )


async def fetch_rodent(client, boro, block, lot, limit):
    return await _query(
        client, DATASET["rodent"],
        where=f"boro_code='{boro}' AND block='{block}' AND lot='{lot}'",
        select="inspection_date,inspection_type,result",
        order="inspection_date DESC", count_col="job_id", limit=limit,
    )


async def _empty_result() -> dict:
    return {"count": 0, "records": []}


async def fetch_building_records(address: str, limit: int = 100) -> dict:
    """Full pipeline: address -> building (with unit count) -> normalized,
    classified records from all four datasets.

    Returns:
      {
        "resolved": bool,
        "building": {"address","bbl","bin","units"} | None,
        "counts":   {"c311","hpd","dob","rodent"},   # accurate totals
        "items":    [ {normalized record}, ... ],     # capped sample per dataset
      }
    """
    async with httpx.AsyncClient(timeout=30) as client:
        building = await geosearch(address, client)
        if not building:
            return {"resolved": False, "building": None, "counts": {}, "items": []}

        boro, block, lot = parse_bbl(building["bbl"])
        bin_ = building.get("bin")
        addr = building["label"]

        units, c311, hpd, dob, rodent = await asyncio.gather(
            fetch_units(client, building["bbl"]),
            fetch_311(client, building["bbl"], limit),
            fetch_hpd(client, boro, block, lot, limit),
            fetch_dob(client, bin_, limit) if bin_ else _empty_result(),
            fetch_rodent(client, boro, block, lot, limit),
        )

    items = (
        [_item_311(r, addr) for r in c311["records"]]
        + [_item_hpd(r, addr) for r in hpd["records"]]
        + [_item_dob(r, addr) for r in dob["records"]]
        + [_item_rodent(r, addr) for r in rodent["records"]]
    )

    return {
        "resolved": True,
        "building": {
            "address": addr,
            "bbl": building["bbl"],
            "bin": bin_,
            "units": units,
        },
        "counts": {
            "c311": c311["count"],
            "hpd": hpd["count"],
            "dob": dob["count"],
            "rodent": rodent["count"],
        },
        "items": items,
    }
