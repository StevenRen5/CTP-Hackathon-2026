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

export default function App() {
  const [status, setStatus] = useState('idle') // idle | loading | done | error
  const [report, setReport] = useState(null)
  const [error, setError] = useState(null)

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

      {status === 'done' && report && <ReportCard report={report} />}
    </div>
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
