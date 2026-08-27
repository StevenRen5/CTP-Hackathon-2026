import { useState } from 'react'

const SEVERITY = {
  high: { label: 'High', className: 'sev sev-high' },
  med: { label: 'Medium', className: 'sev sev-med' },
  low: { label: 'Low', className: 'sev sev-low' },
}

const DATASET_LABEL = {
  '311': '311',
  hpd: 'HPD',
  dob: 'DOB',
  rodent: 'Rodent',
}

// hard coded sample data to be returned to the frontend after reading visible text on apartment page
const SAMPLE_REPORT = {
  address: '123 Sample Avenue, Brooklyn, NY 11215',
  bbl: '3012347501',
  grade: 'B',
  headline: 'Generally well-maintained building with a few issues worth asking about.',
  issues: [
    { tag: '311', severity: 'med', text: 'Several heat and hot-water complaints were reported during winter months.' },
    { tag: 'hpd', severity: 'low', text: 'A small number of apartment maintenance complaints appear in the record.' },
    { tag: 'dob', severity: 'low', text: 'No recent major construction violations were found.' },
  ],
  counts: { c311: 14, hpd: 3, dob: 1, rodent: 0 },
}

// chat bot sample responses
const SAMPLE_ANSWERS = [
  {
    matches: ['heat', 'warm', 'hot water'],
    answer: 'The records suggest this is worth asking about. Several heat and hot-water complaints were reported during winter months, so ask the landlord how quickly those issues were resolved and whether the building has a recent heating inspection.',
  },
  {
    matches: ['noise', 'noisy', 'loud'],
    answer: 'The available building records do not measure everyday street noise. This listing is on a residential Brooklyn block, so visit at two different times of day and ask a current resident about traffic, nightlife, and construction noise.',
  },
  {
    matches: ['safe', 'safety', 'crime'],
    answer: 'This report does not include a crime or personal-safety score. It shows a small number of maintenance records, but you should still visit the block and check current neighborhood data before deciding.',
  },
]

export default function App() {
  const [status, setStatus] = useState('idle') // idle | loading | done | error
  const [report, setReport] = useState(null)
  const [error, setError] = useState(null)
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState([])
  const [chatStatus, setChatStatus] = useState('idle')

  function analyze() {
    setStatus('loading')
    setError(null)

    // Restore this request when the backend is available.
    // chrome.runtime.sendMessage({ type: 'ANALYZE' }, (resp) => {
    //   if (chrome.runtime.lastError) {
    //     setStatus('error')
    //     setError(chrome.runtime.lastError.message)
    //     return
    //   }
    //   if (!resp?.ok) {
    //     setStatus('error')
    //     setError(resp?.error || 'Unknown error')
    //     return
    //   }
    //   setReport(resp.data)
    //   setStatus('done')
    // })

    window.setTimeout(() => {
      setReport(SAMPLE_REPORT)
      setStatus('done')
    }, 500)
  }

  function askQuestion(event) {
    event.preventDefault()
    const trimmedQuestion = question.trim()
    if (!trimmedQuestion || chatStatus === 'loading') return

    setMessages((current) => [...current, { role: 'user', text: trimmedQuestion }])
    setQuestion('')
    setChatStatus('loading')

    window.setTimeout(() => {
      const normalizedQuestion = trimmedQuestion.toLowerCase()
      const matchedAnswer = SAMPLE_ANSWERS.find(({ matches }) =>
        matches.some((match) => normalizedQuestion.includes(match)),
      )
      const answer = matchedAnswer?.answer || 'I do not have enough building-specific data to answer that yet. Try asking about heat, hot water, noise, maintenance, or safety.'
      setMessages((current) => [...current, { role: 'assistant', text: answer }])
      setChatStatus('done')
    }, 450)
  }

  return (
    <div className="app">
      <header className="topbar">
        <span className="mark">🏙️</span>
        <div>
          <h1>Building Report Card</h1>
          <p className="tagline">Real NYC records. Plain-English verdict.</p>
        </div>
      </header>

      <button className="analyze" onClick={analyze} disabled={status === 'loading'}>
        {status === 'loading' ? 'Reading the building…' : 'Analyze this listing'}
      </button>

      {status === 'error' && (
        <div className="error">
          <strong>Couldn’t build the report.</strong>
          <p>{error}</p>
          <p className="hint">Is the backend running on localhost:8000?</p>
        </div>
      )}

      {status === 'idle' && (
        <p className="empty">
          Open a Zillow or StreetEasy listing, then hit analyze.
        </p>
      )}

      {status === 'done' && report && (
        <>
          <ReportCard report={report} />
          <Chat
            messages={messages}
            question={question}
            chatStatus={chatStatus}
            onQuestionChange={setQuestion}
            onAsk={askQuestion}
          />
        </>
      )}
    </div>
  )
}

function Chat({ messages, question, chatStatus, onQuestionChange, onAsk }) {
  return (
    <section className="chat" aria-labelledby="chat-title">
      <div className="chat-head">
        <div>
          <p className="eyebrow">Ask about this building</p>
          <h2 id="chat-title">What else do you want to know?</h2>
        </div>
        <span className="chat-status">Sample answers</span>
      </div>

      {messages.length > 0 && (
        <div className="messages" aria-live="polite">
          {messages.map((message, index) => (
            <div key={`${message.role}-${index}`} className={`message message-${message.role}`}>
              <span className="message-label">{message.role === 'user' ? 'You' : 'Report'}</span>
              <p>{message.text}</p>
            </div>
          ))}
        </div>
      )}

      <form className="chat-form" onSubmit={onAsk}>
        <input
          aria-label="Ask a question about this building"
          value={question}
          onChange={(event) => onQuestionChange(event.target.value)}
          placeholder="Is the heat reliable?"
          disabled={chatStatus === 'loading'}
        />
        <button type="submit" disabled={!question.trim() || chatStatus === 'loading'}>
          {chatStatus === 'loading' ? '...' : 'Ask'}
        </button>
      </form>
      <p className="chat-note">Answers are based on the current report.</p>
    </section>
  )
}

function ReportCard({ report }) {
  const { address, bbl, grade, headline, issues = [], counts = {} } = report
  return (
    <div className="card">
      <div className="card-head">
        <div className={`grade grade-${gradeClass(grade)}`}>{grade}</div>
        <div className="addr">
          <div className="addr-line">{address}</div>
          {bbl && <div className="bbl">BBL {bbl}</div>}
        </div>
      </div>

      {headline && <p className="headline">{headline}</p>}

      <ul className="issues">
        {issues.map((it, i) => (
          <li key={i} className="issue">
            <span className="tag">{DATASET_LABEL[it.tag] || it.tag}</span>
            <span className="issue-text">{it.text}</span>
            <span className={(SEVERITY[it.severity] || SEVERITY.low).className}>
              {(SEVERITY[it.severity] || SEVERITY.low).label}
            </span>
          </li>
        ))}
        {issues.length === 0 && (
          <li className="issue none">No notable issues on record. 🎉</li>
        )}
      </ul>

      <div className="counts">
        <Count label="311" n={counts.c311} />
        <Count label="HPD" n={counts.hpd} />
        <Count label="DOB" n={counts.dob} />
        <Count label="Rodent" n={counts.rodent} />
      </div>
    </div>
  )
}

function Count({ label, n }) {
  return (
    <div className="count">
      <div className="count-n">{n ?? '–'}</div>
      <div className="count-l">{label}</div>
    </div>
  )
}

function gradeClass(grade = '') {
  const g = grade[0]?.toUpperCase()
  if (g === 'A') return 'a'
  if (g === 'B') return 'b'
  if (g === 'C') return 'c'
  return 'd'
}
