import './SessionCatalog.css'

export function saveSessionToStorage({ session_id, subject, chunks_stored }) {
  const raw = localStorage.getItem('socratic_sessions')
  const sessions = raw ? JSON.parse(raw) : []
  const existing = sessions.findIndex(s => s.session_id === session_id)
  const entry = {
    session_id,
    subject,
    chunks_stored,
    created_at: new Date().toISOString(),
    message_count: 0,
  }
  if (existing >= 0) {
    sessions[existing] = { ...sessions[existing], ...entry }
  } else {
    sessions.unshift(entry)
  }
  localStorage.setItem('socratic_sessions', JSON.stringify(sessions.slice(0, 50)))
}

export function bumpMessageCount(session_id) {
  const raw = localStorage.getItem('socratic_sessions')
  if (!raw) return
  const sessions = JSON.parse(raw)
  const idx = sessions.findIndex(s => s.session_id === session_id)
  if (idx >= 0) {
    sessions[idx].message_count = (sessions[idx].message_count || 0) + 1
    localStorage.setItem('socratic_sessions', JSON.stringify(sessions))
  }
}

export function loadSessions() {
  const raw = localStorage.getItem('socratic_sessions')
  return raw ? JSON.parse(raw) : []
}

export function deleteSession(session_id) {
  const raw = localStorage.getItem('socratic_sessions')
  if (!raw) return
  const sessions = JSON.parse(raw).filter(s => s.session_id !== session_id)
  localStorage.setItem('socratic_sessions', JSON.stringify(sessions))
}

function timeAgo(isoString) {
  const diff = Date.now() - new Date(isoString).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

export default function SessionCatalog({ sessions, onResume, onDelete }) {
  if (sessions.length === 0) return null

  return (
    <div className="sc-root">
      <h3 className="sc-heading">Recent Sessions</h3>
      <ul className="sc-list">
        {sessions.map(s => (
          <li key={s.session_id} className="sc-item">
            <button className="sc-resume-btn" onClick={() => onResume(s)}>
              <span className="sc-subject">{s.subject}</span>
              <span className="sc-meta">
                {s.message_count > 0 ? `${s.message_count} messages · ` : ''}
                {timeAgo(s.created_at)}
              </span>
            </button>
            <button
              className="sc-delete-btn"
              title="Remove from history"
              onClick={e => { e.stopPropagation(); onDelete(s.session_id) }}
            >
              ×
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
