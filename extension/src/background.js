// Service worker: the extension's only bridge to the backend.
//  ANALYZE — grab the current tab's URL + text, POST /report, return the card.
//  CHAT    — POST /chat with an address + question, return the answer.

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

async function post(path, body) {
  const res = await fetch(`${BACKEND}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => null)
    throw new Error(detail?.detail || `Backend ${res.status}`)
  }
  return res.json()
}

async function handleAnalyze() {
  const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true })
  if (!tab?.id) throw new Error('No active tab found.')

  const [{ result: page }] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: grabPage,
  })
  console.log('[BRC] grabbed URL:', page.url)

  const data = await post('/report', { page_text: page.text, page_url: page.url })
  console.log('[BRC] report:', data.address, '->', data.grade)
  return data
}

async function handleChat(address, question) {
  return post('/chat', { address, question })
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  const work =
    msg?.type === 'ANALYZE'
      ? handleAnalyze()
      : msg?.type === 'CHAT'
        ? handleChat(msg.address, msg.question)
        : null

  if (!work) return

  work
    .then((data) => sendResponse({ ok: true, data }))
    .catch((err) => {
      console.error('[BRC]', msg.type, 'failed:', err)
      sendResponse({ ok: false, error: String(err?.message || err) })
    })

  return true // keep the message channel open for the async reply
})
