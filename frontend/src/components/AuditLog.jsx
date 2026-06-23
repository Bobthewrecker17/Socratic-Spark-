import './AuditLog.css'

function fmtDate(ts) {
  return new Date(ts).toLocaleString()
}

const MODE_INFO = {
  discovery: { label: 'Discovery', icon: '🔭', desc: 'Explores deeper connections beyond the material' },
  strict:    { label: 'Strict',    icon: '📋', desc: 'Stays within the curriculum' },
}

export default function AuditLog({ data, onModeChange }) {
  const { session, messages, blocked_attempts } = data
  const mode = session.mode || 'discovery'
  const otherMode = mode === 'discovery' ? 'strict' : 'discovery'

  return (
    <div className="al-root">
      <div className="al-header">
        <div>
          <h2 className="al-title">{session.subject}</h2>
          <p className="al-subtitle">Session ID: <code>{session.session_id}</code></p>
          <p className="al-subtitle">Created: {fmtDate(session.created_at)}</p>
        </div>
        <div className="al-stats">
          <div className="al-stat">
            <span className="al-stat-num">{messages.filter(m => m.role === 'user').length}</span>
            <span className="al-stat-label">Student Msgs</span>
          </div>
          <div className="al-stat">
            <span className="al-stat-num al-danger">{blocked_attempts.length}</span>
            <span className="al-stat-label">Blocked</span>
          </div>
          <div className="al-stat">
            <span className="al-stat-num al-warning">
              {messages.reduce((acc, m) => acc + (m.validator_retries || 0), 0)}
            </span>
            <span className="al-stat-label">Retries</span>
          </div>
        </div>
      </div>

      {/* Per-session mode control */}
      <div className={`al-mode-bar mode-${mode}`}>
        <div className="al-mode-left">
          <span className="al-mode-icon">{MODE_INFO[mode].icon}</span>
          <div>
            <span className="al-mode-name">{MODE_INFO[mode].label} Mode</span>
            <span className="al-mode-desc"> — {MODE_INFO[mode].desc}</span>
          </div>
        </div>
        {onModeChange && (
          <button
            className="al-mode-switch-btn"
            onClick={() => onModeChange(otherMode)}
            title={`Switch to ${MODE_INFO[otherMode].label} mode`}
          >
            Switch to {MODE_INFO[otherMode].icon} {MODE_INFO[otherMode].label}
          </button>
        )}
      </div>

      <section className="al-section">
        <h3 className="al-section-title">Conversation Log</h3>
        {messages.length === 0 ? (
          <p className="al-empty">No messages yet.</p>
        ) : (
          <ul className="al-messages">
            {messages.map(m => (
              <li
                key={m.id}
                className={`al-msg ${m.role} ${m.was_blocked ? 'was-blocked' : ''} ${m.validator_retries > 0 ? 'had-retries' : ''}`}
              >
                <div className="al-msg-header">
                  <span className="al-role">{m.role === 'user' ? '🧑 Student' : '🤖 Tutor'}</span>
                  <span className="al-ts">{fmtDate(m.timestamp)}</span>
                  {m.was_blocked && <span className="al-tag blocked">BLOCKED</span>}
                  {m.validator_retries > 0 && (
                    <span className="al-tag retried">{m.validator_retries} retr{m.validator_retries === 1 ? 'y' : 'ies'}</span>
                  )}
                </div>
                <p className="al-msg-content">{m.content}</p>
              </li>
            ))}
          </ul>
        )}
      </section>

      {blocked_attempts.length > 0 && (
        <section className="al-section">
          <h3 className="al-section-title al-danger-title">Blocked Attempts</h3>
          <ul className="al-blocked-list">
            {blocked_attempts.map(b => (
              <li key={b.id} className="al-blocked-item">
                <div className="al-msg-header">
                  <span className="al-tag blocked">BLOCKED</span>
                  <span className="al-ts">{fmtDate(b.timestamp)}</span>
                </div>
                <p className="al-msg-content">{b.content}</p>
                {b.reason && <p className="al-reason">Reason: {b.reason}</p>}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
