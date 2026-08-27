"""NYC Open Data fetchers.

Given a street address, resolve it to a building (BBL + BIN via NYC GeoSearch),
then pull that building's records from four datasets:

  311 Service Requests        erm2-nwe9   filter: bbl
  HPD Violations              wvxf-dwi5   filter: boroid + block + lot (strings)
  DOB Permit Issuance         ipu4-2q9a   filter: bin__
  DOHMH Rodent Inspection     p937-wjvj   filter: boro_code + block + lot (strings)

BBL (Borough-Block-Lot) is the shared key. A BBL like "3017640001" means
borough 3, block 1764, lot 1 — note the block/lot fields in HPD and Rodent are
strings with leading zeros stripped.
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
}


def _socrata_headers() -> dict:
    # An app token is optional but lifts rate limits. Set SOCRATA_APP_TOKEN in .env.
    token = os.environ.get("SOCRATA_APP_TOKEN")
    return {"X-App-Token": token} if token else {}


def parse_bbl(bbl: str) -> tuple[str, str, str]:
    """'3017640001' -> ('3', '1764', '1'). Strips leading zeros from block/lot
    to match how HPD and Rodent store them."""
    return bbl[0], str(int(bbl[1:6])), str(int(bbl[6:10]))


async def geosearch(address: str, client: httpx.AsyncClient) -> dict | None:
    """Resolve a free-text address to a building. Returns bbl/bin/label, or None.

    GeoSearch occasionally 503s; retry a couple of times before giving up.
    """
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
            return {
                "bbl": pad.get("bbl"),
                "bin": pad.get("bin"),
                "label": props.get("label"),
            }
        except (httpx.HTTPStatusError, httpx.TransportError):
            if attempt == 2:
                raise
            await asyncio.sleep(0.6)
    return None


async def _query(
    client: httpx.AsyncClient,
    dataset_id: str,
    where: str,
    select: str,
    order: str,
    count_col: str,
    limit: int,
) -> dict:
    """Run a records query and a count query for one dataset, concurrently.
    Returns {"count": int, "records": [...]}."""
    base = f"{SOCRATA}/{dataset_id}.json"
    headers = _socrata_headers()

    records_params = {"$where": where, "$select": select, "$order": order, "$limit": limit}
    count_params = {"$where": where, "$select": f"count({count_col})"}

    records_res, count_res = await asyncio.gather(
        client.get(base, params=records_params, headers=headers),
        client.get(base, params=count_params, headers=headers),
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
        select="created_date,complaint_type,descriptor,status,resolution_description,incident_address",
        order="created_date DESC",
        count_col="unique_key",
        limit=limit,
    )


async def fetch_hpd(client, boro, block, lot, limit):
    return await _query(
        client, DATASET["hpd"],
        where=f"boroid='{boro}' AND block='{block}' AND lot='{lot}'",
        select="inspectiondate,novissueddate,class,novdescription,violationstatus,currentstatus,apartment",
        order="inspectiondate DESC",
        count_col="violationid",
        limit=limit,
    )


async def fetch_dob(client, bin_, limit):
    return await _query(
        client, DATASET["dob"],
        where=f"bin__='{bin_}'",
        select="issuance_date,filing_date,job_type,permit_type,permit_subtype,permit_status,work_type",
        order="issuance_date DESC",
        count_col="job__",
        limit=limit,
    )


async def fetch_rodent(client, boro, block, lot, limit):
    return await _query(
        client, DATASET["rodent"],
        where=f"boro_code='{boro}' AND block='{block}' AND lot='{lot}'",
        select="inspection_date,inspection_type,result",
        order="inspection_date DESC",
        count_col="job_id",
        limit=limit,
    )


async def fetch_building_records(
    address: str, limit: int = 100
) -> dict:
    """Full pipeline: address -> building -> records from all four datasets.

    Returns:
      {
        "resolved": bool,
        "building": {"bbl","bin","label"} | None,
        "counts":   {"c311","hpd","dob","rodent"},
        "records":  {"c311":[...], "hpd":[...], "dob":[...], "rodent":[...]},
      }
    """
    async with httpx.AsyncClient(timeout=30) as client:
        building = await geosearch(address, client)
        if not building:
            return {"resolved": False, "building": None, "counts": {}, "records": {}}

        boro, block, lot = parse_bbl(building["bbl"])
        bin_ = building.get("bin")

        # DOB needs a BIN; skip gracefully if GeoSearch didn't provide one.
        dob_task = (
            fetch_dob(client, bin_, limit)
            if bin_
            else _empty_result()
        )

        c311, hpd, dob, rodent = await asyncio.gather(
            fetch_311(client, building["bbl"], limit),
            fetch_hpd(client, boro, block, lot, limit),
            dob_task,
            fetch_rodent(client, boro, block, lot, limit),
        )

    return {
        "resolved": True,
        "building": building,
        "counts": {
            "c311": c311["count"],
            "hpd": hpd["count"],
            "dob": dob["count"],
            "rodent": rodent["count"],
        },
        "records": {
            "c311": c311["records"],
            "hpd": hpd["records"],
            "dob": dob["records"],
            "rodent": rodent["records"],
        },
    }


async def _empty_result() -> dict:
    return {"count": 0, "records": []}
