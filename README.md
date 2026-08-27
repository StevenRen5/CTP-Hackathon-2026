# Blockr — Building Report Card

A Chrome extension that gives any NYC apartment listing a report card on the building — using real NYC open data (311 complaints, housing violations, permits, rodent inspections).

Works on **NYC listings only**.

## Setup

**1. Run the backend** (needs Python 3.11+ and a free [Gemini API key](https://aistudio.google.com/apikey)):

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env      # paste your Gemini key into .env
.venv/bin/uvicorn main:app
```

**2. Load the extension:**
- Go to `chrome://extensions` → turn on **Developer mode**
- Click **Load unpacked** → select the `extension/dist` folder

## Use it

Open a NYC listing on Zillow, click the Blockr icon, and hit **Analyze this listing**. Then ask the chat box anything.

> Keep the backend running — the extension needs it on `localhost:8000`.
