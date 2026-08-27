import os
import sys
import time

from google import genai
from google.genai import types


PROMPT = """
hi whats up chat
"""


def main() -> None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        sys.exit("GEMINI_API_KEY is not set.")

    client = genai.Client(api_key=api_key)
    print(f"Prompt:\n{PROMPT}")

    started_at = time.perf_counter()
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=PROMPT,
        config=types.GenerateContentConfig(
            temperature=0,
            max_output_tokens=100,
        ),
    )
    elapsed_seconds = time.perf_counter() - started_at

    if not response.text:
        sys.exit("Gemini returned no text.")

    print(f"Reply:\n{response.text.strip()}")
    print(f"\nResponse time: {elapsed_seconds:.2f} seconds")


if __name__ == "__main__":
    main()
