"""Standalone test for the NYC data pipeline — no server needed.

    cd backend
    python test_records.py [address]

Resolves an address to a building and pulls normalized, classified records from
all four NYC datasets. Hits live NYC Open Data + GeoSearch, so it needs network.
"""

import asyncio
import json
import sys

from nyc import fetch_building_records

DEFAULT_ADDRESS = "1296 Nostrand Ave, Brooklyn, NY 11226"


async def main():
    address = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ADDRESS
    print(f"Fetching NYC records for: {address}\n")

    out = await fetch_building_records(address, limit=5)
    if not out["resolved"]:
        print("Could not resolve that address to an NYC building.")
        return

    b = out["building"]
    print(f"Address : {b['address']}")
    print(f"BBL/BIN : {b['bbl']} / {b['bin']}")
    print(f"Units   : {b['units']}")
    print(f"Counts  : {json.dumps(out['counts'])}")
    print(f"Items   : {len(out['items'])} normalized records\n")

    for it in out["items"]:
        sev = f"[{it['severity']}]" if it["severity"] else ""
        print(f"  ({it['source']}/{it['classification']}){sev} {it['description'][:70]}")
        print(f"      reported={it['date_reported']} resolved={it['date_resolved']} due={it['date_expected_resolve']}")


if __name__ == "__main__":
    asyncio.run(main())
