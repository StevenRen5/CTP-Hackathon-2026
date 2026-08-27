// Service worker: the extension's only bridge to the backend.
// The side panel asks it to analyze the current tab; it grabs the page URL +
// text, POSTs to FastAPI /report, and returns the full graded report card.

const BACKEND = 'http://localhost:8000'

// Toolbar-icon click opens the side panel.
chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .catch((err) => console.error('[BRC] sidePanel behavior:', err))

// Runs *inside* the listing page. Keep it dependency-free — it's injected as a
// standalone function, not bundled. The URL is the primary signal (Zillow puts
// the address in the /homedetails/ slug); innerText is a fallback.
function grabPage() {
  return {
    url: location.href,
    text: document.body.innerText.slice(0, 20000),
  }
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

      const [{ result: page }] = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: grabPage,
      })
      console.log('[BRC] grabbed URL:', page.url)

      const res = await fetch(`${BACKEND}/report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ page_text: page.text, page_url: page.url }),
      })
      if (!res.ok) {
        const detail = await res.json().catch(() => null)
        throw new Error(detail?.detail || `Backend ${res.status}`)
      }

      const data = await res.json()
      console.log('[BRC] report:', data.address, '->', data.grade)

      sendResponse({ ok: true, data })
    } catch (err) {
      console.error('[BRC] analyze failed:', err)
      sendResponse({ ok: false, error: String(err?.message || err) })
    }
  })()

  return true // keep the message channel open for the async reply
})
