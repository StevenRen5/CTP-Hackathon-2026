"""Quick standalone test for address extraction — no extension, no server needed.

    cd backend
    python test_extract.py

Feeds deliberately noisy 'page text' (the real property buried in nav/ads/
nearby-listings junk) to Gemini and prints what it pulls out.
"""

from dotenv import load_dotenv

load_dotenv()

from gemini import extract_address

# Mimics what the content script grabs: the real listing plus a lot of noise.
SAMPLE_PAGE_TEXT = """
Zillow  Buy  Rent  Sell  Home Loans  Agent finder  Manage Rentals  Sign in
Skip main navigation

For rent  ·  $3,450/mo
248 Nostrand Ave APT 3R, Brooklyn, NY 11205
2 beds  1 bath  850 sqft
Bedford-Stuyvesant

Overview
Charming pre-war 2-bedroom in the heart of Bed-Stuy. Hardwood floors,
south-facing windows, steps from the G train.

Listed by:
Jane Broker, Awesome Realty LLC
Office: 55 Water St, New York, NY 10041

Nearby homes for sale
300 Marcy Ave, Brooklyn, NY 11211 — $4,100/mo
19 Kosciuszko St, Brooklyn, NY 11216 — $2,900/mo

Advertisement — Refinance today at 55 Wall Street!

Zillow Group  ·  About  ·  Privacy  ·  Terms
"""


def main():
    print("Extracting address from sample page text...\n")
    result = extract_address(SAMPLE_PAGE_TEXT)
    print(f"  found       : {result.found}")
    print(f"  full_address: {result.full_address}")
    print(f"  street      : {result.street}")
    print(f"  city        : {result.city}")
    print(f"  borough     : {result.borough}")
    print(f"  state       : {result.state}")
    print(f"  zip         : {result.zip}")
    print()

    expected = "248 Nostrand"
    if expected in result.full_address:
        print(f"PASS — picked the property, not the brokerage or a nearby listing.")
    else:
        print(f"CHECK — expected the address to contain '{expected}'.")


if __name__ == "__main__":
    main()
