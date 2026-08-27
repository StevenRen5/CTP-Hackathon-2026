import { useState, type ChangeEvent, type FormEvent } from 'react'

type ReportStatus = 'idle' | 'loading' | 'done' | 'error'
type ChatStatus = 'idle' | 'loading' | 'done'

type Category = {
  score: number
  max: number
  direction?: string
  explanation: string
}

type Report = {
  address: string
  bbl: string
  units: number | null
  grade: string
  score: number
  confidence: string
  headline: string
  summary: string
  prospects: string
  caveats: string[]
  categories: {
    safety: Category
    building_conditions: Category
    pests: Category
    responsiveness: Category
    trend: Category
  }
  counts: Partial<{ c311: number; hpd: number; dob: number; rodent: number }>
}

type Message = {
  role: 'user' | 'assistant'
  text: string
}

const CATEGORY_LABEL: Record<keyof Report['categories'], string> = {
  safety: 'Safety',
  building_conditions: 'Building conditions',
  pests: 'Pests',
  responsiveness: 'Responsiveness',
  trend: 'Recent trend',
}

const CATEGORY_ORDER: Array<keyof Report['categories']> = [
  'safety',
  'building_conditions',
  'pests',
  'responsiveness',
  'trend',
]

const DATASET_INFO = {
  '311': { name: 'NYC 311', description: 'Housing complaints' },
  hpd: { name: 'HPD', description: 'Housing violations' },
  dob: { name: 'DOB', description: 'Building permits' },
  rodent: { name: 'Rodent', description: 'Pest inspections' },
}

export default function App() {
  const [status, setStatus] = useState<ReportStatus>('idle')
  const [report, setReport] = useState<Report | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [chatStatus, setChatStatus] = useState<ChatStatus>('idle')

  function analyze() {
    setStatus('loading')
    setError(null)

    // Ask the service worker to grab the current tab and run the full pipeline
    // (extract -> records -> score -> explanation) via the backend /report.
    chrome.runtime.sendMessage({ type: 'ANALYZE' }, (resp) => {
      if (chrome.runtime.lastError) {
        setStatus('error')
        setError(chrome.runtime.lastError.message ?? 'Extension messaging error')
        return
      }
      if (!resp?.ok) {
        setStatus('error')
        setError(resp?.error || 'Unknown error')
        return
      }
      setReport(resp.data as Report)
      setStatus('done')
    })
  }

  function askQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmedQuestion = question.trim()
    if (!trimmedQuestion || chatStatus === 'loading' || !report) return

    setMessages((current) => [...current, { role: 'user', text: trimmedQuestion }])
    setQuestion('')
    setChatStatus('loading')

    // Answered by the backend /chat, grounded in this building's NYC records.
    chrome.runtime.sendMessage(
      { type: 'CHAT', address: report.address, question: trimmedQuestion },
      (resp) => {
        if (chrome.runtime.lastError || !resp?.ok) {
          const detail = chrome.runtime.lastError?.message || resp?.error || 'Something went wrong.'
          setMessages((current) => [...current, { role: 'assistant', text: `Sorry — ${detail}` }])
          setChatStatus('done')
          return
        }
        setMessages((current) => [...current, { role: 'assistant', text: resp.data.answer }])
        setChatStatus('done')
      },
    )
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
          <p className="hint">Make sure the backend is running on localhost:8000, and you’re on a NYC listing.</p>
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

type ChatProps = {
  messages: Message[]
  question: string
  chatStatus: ChatStatus
  onQuestionChange: (value: string) => void
  onAsk: (event: FormEvent<HTMLFormElement>) => void
}

function Chat({ messages, question, chatStatus, onQuestionChange, onAsk }: ChatProps) {
  return (
    <section className="chat" aria-labelledby="chat-title">
      <div className="chat-head">
        <div>
          <p className="eyebrow">Ask about this building</p>
          <h2 id="chat-title">What else do you want to know?</h2>
        </div>
        <span className="chat-status">Grounded in records</span>
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
          onChange={(event: ChangeEvent<HTMLInputElement>) => onQuestionChange(event.target.value)}
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

function ReportCard({ report }: { report: Report }) {
  const { address, bbl, units, grade, score, confidence, headline, summary, caveats = [], categories, counts = {} } = report
  return (
    <div className="card">
      <div className="card-head">
        <div className={`grade grade-${gradeClass(grade)}`}>{grade}</div>
        <div className="addr">
          <div className="addr-line">{address}</div>
          <div className="addr-meta">
            {typeof score === 'number' && <span>Score {score}/100</span>}
            {units != null && <span>{units} units</span>}
            {confidence && <span>{confidence} confidence</span>}
          </div>
          {bbl && <div className="bbl">BBL {bbl}</div>}
        </div>
      </div>

      {headline && <p className="headline">{headline}</p>}
      {summary && <p className="summary">{summary}</p>}

      <div className="categories">
        {CATEGORY_ORDER.map((key) => (
          <CategoryBar key={key} label={CATEGORY_LABEL[key]} category={categories[key]} />
        ))}
      </div>

      <div className="counts">
        <Count info={DATASET_INFO['311']} n={counts.c311} />
        <Count info={DATASET_INFO.hpd} n={counts.hpd} />
        <Count info={DATASET_INFO.dob} n={counts.dob} />
        <Count info={DATASET_INFO.rodent} n={counts.rodent} />
      </div>

      {caveats.length > 0 && (
        <ul className="caveats">
          {caveats.map((c, i) => (
            <li key={i}>{c}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

function CategoryBar({ label, category }: { label: string; category: Category }) {
  const ratio = category.max > 0 ? category.score / category.max : 0
  const level = ratio >= 0.7 ? 'good' : ratio >= 0.4 ? 'warn' : 'crit'
  return (
    <div className="cat">
      <div className="cat-top">
        <span className="cat-name">{label}</span>
        <span className="cat-score">
          {category.score}
          <span className="cat-max">/{category.max}</span>
        </span>
      </div>
      <div className="cat-track">
        <div className={`cat-fill cat-${level}`} style={{ width: `${Math.round(ratio * 100)}%` }} />
      </div>
      {category.explanation && <p className="cat-text">{category.explanation}</p>}
    </div>
  )
}

function Count({ info, n }: { info: { name: string; description: string }; n?: number }) {
  return (
    <div className="count" title={`${info.name}: ${info.description}`}>
      <div className="count-n">{n ?? '–'}</div>
      <div className="count-name">{info.name}</div>
    </div>
  )
}

function gradeClass(grade = ''): string {
  const g = grade[0]?.toUpperCase()
  if (g === 'A') return 'a'
  if (g === 'B') return 'b'
  if (g === 'C') return 'c'
  if (g === 'D') return 'd'
  return 'f'
}
