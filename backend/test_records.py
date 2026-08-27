"""Standalone test for the NYC data pipeline — no server needed.

    cd backend
    python test_records.py [address]

Resolves an address to a building and pulls counts + sample records from all
four NYC datasets. Hits live NYC Open Data + GeoSearch, so it needs network.
"""

import asyncio
import json
import sys

from nyc import fetch_building_records

DEFAULT_ADDRESS = "248 Nostrand Ave, Brooklyn, NY 11205"


async def main():
    address = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ADDRESS
    print(f"Fetching NYC records for: {address}\n")

    out = await fetch_building_records(address, limit=3)
    if not out["resolved"]:
        print("Could not resolve that address to an NYC building.")
        return

    b = out["building"]
    print(f"Building : {b['label']}")
    print(f"BBL / BIN: {b['bbl']} / {b['bin']}")
    print(f"Counts   : {json.dumps(out['counts'])}\n")

    for key, label in [("c311", "311"), ("hpd", "HPD"), ("dob", "DOB"), ("rodent", "Rodent")]:
        recs = out["records"].get(key, [])
        print(f"--- {label}: {out['counts'].get(key, 0)} total, showing {len(recs)} ---")
        for r in recs:
            print("   ", json.dumps(r))
        print()


if __name__ == "__main__":
    asyncio.run(main())
