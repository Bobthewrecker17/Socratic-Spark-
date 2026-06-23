import { useState, useEffect } from 'react'
import AuditLog from '../components/AuditLog.jsx'
import './TeacherView.css'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const MODE_INFO = {
  discovery: {
    label: 'Discovery',
    description: 'Goes deeper — tutor can explore related concepts and broader connections beyond the material to enrich understanding.',
    icon: '🔭',
  },
  strict: {
    label: 'Strict',
    description: 'Curriculum-bounded — every question and hint stays within the concepts explicitly covered in the uploaded material. Best for exam prep.',
    icon: '📋',
  },
}

export default function TeacherView() {
  const [password, setPassword] = useState('')
  const [authed, setAuthed] = useState(false)
  const [authError, setAuthError] = useState('')
  const [sessions, setSessions] = useState([])
  const [loadingList, setLoadingList] = useState(false)
  const [selectedSession, setSelectedSession] = useState(null)
  const [auditData, setAuditData] = useState(null)
  const [loadingAudit, setLoadingAudit] = useState(false)
  const [defaultMode, setDefaultMode] = useState('discovery')
  const [savingMode, setSavingMode] = useState(false)

  async function handleLogin(e) {
    e.preventDefault()
    setAuthError('')
    setLoadingList(true)
    try {
      const [sessRes, settRes] = await Promise.all([
        fetch(`${API}/audit/sessions`, { headers: { Authorization: `Bearer ${password}` } }),
        fetch(`${API}/audit/settings`, { headers: { Authorization: `Bearer ${password}` } }),
      ])
      if (sessRes.status === 401) { setAuthError('Incorrect password.'); return }
      const sessData = await sessRes.json()
      const settData = await settRes.json()
      setSessions(sessData.sessions)
      setDefaultMode(settData.default_mode || 'discovery')
      setAuthed(true)
    } catch {
      setAuthError('Could not connect to server.')
    } finally {
      setLoadingList(false)
    }
  }

  async function saveDefaultMode(mode) {
    setSavingMode(true)
    try {
      await fetch(`${API}/audit/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${password}` },
        body: JSON.stringify({ default_mode: mode }),
      })
      setDefaultMode(mode)
    } finally {
      setSavingMode(false)
    }
  }

  async function patchSessionMode(sessionId, mode) {
    await fetch(`${API}/audit/${sessionId}/mode`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${password}` },
      body: JSON.stringify({ mode }),
    })
    // Update local audit data immediately
    setAuditData(prev => prev ? { ...prev, session: { ...prev.session, mode } } : prev)
    // Refresh session list badge
    setSessions(prev => prev.map(s => s.session_id === sessionId ? { ...s, mode } : s))
  }

  async function loadAudit(sessionId) {
    setSelectedSession(sessionId)
    setLoadingAudit(true)
    try {
      const res = await fetch(`${API}/audit/${sessionId}`, {
        headers: { Authorization: `Bearer ${password}` },
      })
      setAuditData(await res.json())
    } catch {
      setAuditData(null)
    } finally {
      setLoadingAudit(false)
    }
  }

  async function refreshSessions() {
    setLoadingList(true)
    try {
      const res = await fetch(`${API}/audit/sessions`, { headers: { Authorization: `Bearer ${password}` } })
      const data = await res.json()
      setSessions(data.sessions)
    } finally {
      setLoadingList(false)
    }
  }

  if (!authed) {
    return (
      <div className="tv-login-wrap">
        <div className="tv-login-card">
          <h2>Teacher Dashboard</h2>
          <p>Enter your password to view session audits.</p>
          <form onSubmit={handleLogin} className="tv-login-form">
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              autoFocus
            />
            {authError && <span className="tv-error">{authError}</span>}
            <button type="submit" disabled={loadingList}>
              {loadingList ? 'Logging in…' : 'Log In'}
            </button>
          </form>
        </div>
      </div>
    )
  }

  return (
    <div className="tv-layout">
      <div className="tv-sessions-panel">
        {/* Global mode toggle */}
        <div className="tv-mode-section">
          <div className="tv-mode-label">Default Tutor Mode</div>
          <div className="tv-mode-toggle">
            {Object.entries(MODE_INFO).map(([key, info]) => (
              <button
                key={key}
                className={`tv-mode-btn ${defaultMode === key ? 'active ' + key : ''}`}
                onClick={() => saveDefaultMode(key)}
                disabled={savingMode}
                title={info.description}
              >
                {info.icon} {info.label}
              </button>
            ))}
          </div>
          <p className="tv-mode-desc">{MODE_INFO[defaultMode].description}</p>
        </div>

        <div className="tv-panel-header">
          <h3>Sessions</h3>
          <button className="tv-refresh-btn" onClick={refreshSessions} disabled={loadingList}>
            {loadingList ? '…' : '↻'}
          </button>
        </div>

        {sessions.length === 0 ? (
          <p className="tv-empty">No sessions yet.</p>
        ) : (
          <ul className="tv-session-list">
            {sessions.map(s => (
              <li
                key={s.session_id}
                className={`tv-session-item ${selectedSession === s.session_id ? 'active' : ''}`}
                onClick={() => loadAudit(s.session_id)}
              >
                <div className="tv-session-subject">{s.subject}</div>
                <div className="tv-session-meta">
                  <span className="tv-badge neutral">{s.message_count} msgs</span>
                  {s.mode && (
                    <span className={`tv-badge mode-${s.mode}`}>
                      {MODE_INFO[s.mode]?.icon} {MODE_INFO[s.mode]?.label}
                    </span>
                  )}
                  {s.blocked_count > 0 && (
                    <span className="tv-badge danger">{s.blocked_count} blocked</span>
                  )}
                  {s.validator_retry_count > 0 && (
                    <span className="tv-badge warning">{s.validator_retry_count} retries</span>
                  )}
                </div>
                <div className="tv-session-date">
                  {new Date(s.created_at).toLocaleString()}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="tv-audit-panel">
        {!selectedSession && (
          <div className="tv-empty-state">
            <span>Select a session to view its audit log.</span>
          </div>
        )}
        {loadingAudit && <div className="tv-loading">Loading audit log…</div>}
        {!loadingAudit && auditData && (
          <AuditLog
            data={auditData}
            onModeChange={(mode) => patchSessionMode(auditData.session.session_id, mode)}
          />
        )}
      </div>
    </div>
  )
}
