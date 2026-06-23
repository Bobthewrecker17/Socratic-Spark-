import { useState, useEffect } from 'react'
import CurriculumUpload from '../components/CurriculumUpload.jsx'
import ChatWindow from '../components/ChatWindow.jsx'
import {
  saveSessionToStorage,
  bumpMessageCount,
  loadSessions,
  deleteSession,
} from '../components/SessionCatalog.jsx'
import './StudentView.css'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const MODE_META = {
  discovery: { icon: '🔭', label: 'Discovery',  next: 'strict',    nextLabel: '📋 Switch to Strict' },
  strict:    { icon: '📋', label: 'Strict',      next: 'discovery', nextLabel: '🔭 Switch to Discovery' },
}

function timeAgo(isoString) {
  const diff = Date.now() - new Date(isoString).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days < 7) return `${days}d ago`
  return new Date(isoString).toLocaleDateString()
}

export default function StudentView() {
  const [tab, setTab] = useState('new')           // 'new' | 'sessions'
  const [sessionId, setSessionId] = useState(null)
  const [subject, setSubject] = useState('')
  const [sessionMode, setSessionMode] = useState('discovery')
  const [messages, setMessages] = useState([])
  const [thinking, setThinking] = useState(false)
  const [catalog, setCatalog] = useState([])
  const [resuming, setResuming] = useState(false)

  useEffect(() => {
    setCatalog(loadSessions())
  }, [])

  function refreshCatalog() {
    setCatalog(loadSessions())
  }

  async function handleModeSwitch() {
    const next = MODE_META[sessionMode]?.next || 'discovery'
    try {
      await fetch(`${API}/chat/${sessionId}/mode`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: next }),
      })
      setSessionMode(next)
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: `Tutor style switched to **${MODE_META[next].icon} ${MODE_META[next].label}** mode.` },
      ])
    } catch { /* silent */ }
  }

  function handleUpload({ session_id, subject: sub, chunks_stored, mode }) {
    saveSessionToStorage({ session_id, subject: sub, chunks_stored, mode })
    refreshCatalog()
    setSubject(sub)
    setSessionId(session_id)
    setSessionMode(mode || 'discovery')
    setMessages([{
      role: 'assistant',
      content: `Welcome! I'm your Socratic tutor for **${sub}**. I've loaded your curriculum (${chunks_stored} sections). What would you like to explore?`,
    }])
  }

  async function handleResume(entry) {
    setResuming(true)
    setSubject(entry.subject)
    setSessionId(entry.session_id)
    setSessionMode(entry.mode || 'discovery')
    setMessages([{ role: 'assistant', content: 'Loading your previous conversation…' }])
    try {
      const res = await fetch(`${API}/chat/history/${entry.session_id}`)
      const data = await res.json()
      if (data.mode) setSessionMode(data.mode)
      setMessages(
        data.messages?.length > 0
          ? data.messages.map(m => ({ role: m.role, content: m.content }))
          : [{ role: 'assistant', content: `Welcome back to **${entry.subject}**! What would you like to explore?` }]
      )
    } catch {
      setMessages([{ role: 'assistant', content: `Welcome back to **${entry.subject}**! What would you like to explore?` }])
    } finally {
      setResuming(false)
    }
  }

  async function handleSend(text) {
    setMessages(prev => [...prev, { role: 'user', content: text }])
    setThinking(true)
    try {
      const res = await fetch(`${API}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message: text }),
      })
      const data = await res.json()
      if (data.blocked) {
        setMessages(prev => [...prev, { role: 'assistant', content: "Let's keep our focus on the curriculum!", blocked: true }])
      } else {
        setMessages(prev => [...prev, { role: 'assistant', content: data.reply, validatorRetries: data.validator_retries }])
        bumpMessageCount(sessionId)
        refreshCatalog()
      }
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Something went wrong. Please try again.', error: true }])
    } finally {
      setThinking(false)
    }
  }

  function exitSession() {
    setSessionId(null)
    setMessages([])
    refreshCatalog()
  }

  // ── Active chat view ───────────────────────────────────────────────────────
  if (sessionId) {
    return (
      <div className="sv-chat-layout">
        <div className="sv-sidebar">
          <div className="sv-subject-badge">{subject}</div>
          <div className={`sv-mode-badge mode-${sessionMode}`}>
            {MODE_META[sessionMode]?.icon} {MODE_META[sessionMode]?.label}
          </div>
          <button className="sv-mode-switch-btn" onClick={handleModeSwitch}>
            {MODE_META[sessionMode]?.nextLabel}
          </button>
          <p className="sv-sidebar-hint">
            {sessionMode === 'discovery'
              ? "Ask anything — I'll help you go deeper and explore connections beyond the material."
              : "Ask questions about your material — I'll keep every hint strictly within what you've uploaded."}
          </p>
          <button className="sv-restart-btn" onClick={exitSession}>↩ My Sessions</button>
        </div>
        <ChatWindow messages={messages} onSend={handleSend} thinking={thinking || resuming} />
      </div>
    )
  }

  // ── Landing view with tabs ─────────────────────────────────────────────────
  return (
    <div className="sv-container">
      <div className="sv-hero">
        <h1>Socratic Spark</h1>
        <p>Upload your study material and get guided to deeper understanding.</p>
      </div>

      <div className="sv-tabs">
        <button
          className={`sv-tab ${tab === 'new' ? 'active' : ''}`}
          onClick={() => setTab('new')}
        >
          + New Session
        </button>
        <button
          className={`sv-tab ${tab === 'sessions' ? 'active' : ''}`}
          onClick={() => { setTab('sessions'); refreshCatalog() }}
        >
          My Sessions
          {catalog.length > 0 && <span className="sv-tab-count">{catalog.length}</span>}
        </button>
      </div>

      {tab === 'new' && (
        <CurriculumUpload onUpload={handleUpload} />
      )}

      {tab === 'sessions' && (
        <div className="sv-catalog-page">
          {catalog.length === 0 ? (
            <div className="sv-catalog-empty">
              <span className="sv-catalog-empty-icon">📚</span>
              <p>No sessions yet.</p>
              <button className="sv-catalog-start-btn" onClick={() => setTab('new')}>
                Start your first session →
              </button>
            </div>
          ) : (
            <ul className="sv-catalog-list">
              {catalog.map(s => (
                <li key={s.session_id} className="sv-catalog-card">
                  <button className="sv-catalog-resume" onClick={() => handleResume(s)}>
                    <div className="sv-catalog-top">
                      <span className="sv-catalog-subject">{s.subject}</span>
                      <span className={`sv-catalog-mode mode-${s.mode || 'discovery'}`}>
                        {MODE_META[s.mode || 'discovery']?.icon} {MODE_META[s.mode || 'discovery']?.label}
                      </span>
                    </div>
                    <div className="sv-catalog-meta">
                      <span>{s.message_count > 0 ? `${s.message_count} message${s.message_count !== 1 ? 's' : ''}` : 'No messages yet'}</span>
                      <span className="sv-catalog-dot">·</span>
                      <span>{timeAgo(s.created_at)}</span>
                    </div>
                  </button>
                  <button
                    className="sv-catalog-delete"
                    title="Remove from history"
                    onClick={() => { deleteSession(s.session_id); refreshCatalog() }}
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
