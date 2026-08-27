// Service worker: the extension's only bridge to the backend.
// The side panel asks it to analyze the current tab; it grabs the page text,
// POSTs to FastAPI, and returns the report card JSON.

const BACKEND = 'http://localhost:8000'

// Toolbar-icon click opens the side panel.
chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .catch((err) => console.error('[BRC] sidePanel behavior:', err))

// Runs *inside* the listing page. Keep it dependency-free — it's injected as a
// standalone function, not bundled. innerText sidesteps Zillow's obfuscated JSON.
function grabPageText() {
  return document.body.innerText.slice(0, 20000)
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type !== 'ANALYZE') return

  ;(async () => {
    try {
      const [tab] = await chrome.tabs.query({
        active: true,
        lastFocusedWindow: true,
      })
      if (!tab?.id) throw new Error('No active tab found.')

      const [{ result: pageText }] = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: grabPageText,
      })

      const res = await fetch(`${BACKEND}/report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ page_text: pageText }),
      })
      if (!res.ok) throw new Error(`Backend ${res.status}`)

      sendResponse({ ok: true, data: await res.json() })
    } catch (err) {
      console.error('[BRC] analyze failed:', err)
      sendResponse({ ok: false, error: String(err?.message || err) })
    }
  })()

  return true // keep the message channel open for the async reply
})
