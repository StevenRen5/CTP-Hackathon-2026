# Blockr — Building Report Card

A Chrome extension that turns any NYC apartment listing into an honest **report card on the building**, built from real NYC open data. Browse a place on Zillow or StreetEasy, click the icon, and get a graded breakdown of the building's 311 complaints, housing violations, permits, and rodent inspections — in plain English, plus an ask-anything chat.

> Works on **NYC listings only** (the data is NYC open data).

---

## Run it yourself

You need two things running: the **backend** (which holds the API key and talks to NYC's data) and the **extension** loaded in Chrome.

### Prerequisites
- Python 3.11+
- Google Chrome
- A free **Gemini API key** — get one at https://aistudio.google.com/apikey

### 1. Start the backend

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp .env.example .env          # then open .env and paste your Gemini API key
.venv/bin/uvicorn main:app    # runs on http://localhost:8000 — leave this running
```

Check it's up: open http://localhost:8000/health → you should see `{"status":"ok"}`.

> Your key lives only in `backend/.env`, which is git-ignored. Never commit it.

### 2. Load the extension in Chrome

The build is already committed, so there's nothing to compile.

1. Go to `chrome://extensions`
2. Turn on **Developer mode** (top-right)
3. Click **Load unpacked** and select the **`extension/dist`** folder
4. Click the 🧩 puzzle icon in the toolbar and **pin** Blockr

### 3. Use it

1. Open a **NYC** apartment listing on Zillow (a `zillow.com/homedetails/…` page)
2. Click the Blockr icon to open the side panel
3. Hit **Analyze this listing**
4. Read the report card, then ask the chat box anything (e.g. *"Is the heat reliable?"*)

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| **"Couldn't build the report"** | The backend probably isn't running — confirm http://localhost:8000/health responds. |
| **"This tool only covers NYC buildings"** | The listing isn't in the five boroughs. Only NYC addresses resolve. |
| **Extension does nothing / not listed** | Make sure Developer mode is on and you selected `extension/dist` (not `extension`). |
| **Backend error about the key** | Your `GEMINI_API_KEY` is missing or invalid in `backend/.env`. |

---

## How it works

`listing page → extract address (Gemini, from the URL) → resolve to a building (NYC GeoSearch → BBL/BIN) → join 4 NYC datasets (311, HPD, DOB, rodent) → deterministic score → Gemini explains the score → report card + grounded chat`

The **score is computed by rules**, not the AI — Gemini only explains it and answers questions grounded in the records.

## Rebuilding the extension (optional)

Only needed if you change the extension source:

```bash
cd extension
npm install
npm run build      # regenerates extension/dist
```

## Tech stack

Chrome extension (React + TypeScript + Vite/CRXJS, side panel) · Python FastAPI backend · Google Gemini · NYC Open Data (Socrata) + NYC Planning GeoSearch
