import { useState, useRef } from 'react'
import './CurriculumUpload.css'

const API = import.meta.env.VITE_API_URL || 'https://socratic-spark-snaw.onrender.com'

const TUTOR_MODES = [
  {
    key: 'discovery',
    icon: '🔭',
    label: 'Discovery',
    desc: 'We can go deeper — I\'ll help you explore related ideas and connections beyond the material to build real understanding.',
  },
  {
    key: 'strict',
    icon: '📋',
    label: 'Strict',
    desc: 'Stay within the curriculum — every question and hint comes from exactly what\'s in your material. Great for exam prep.',
  },
]

export default function CurriculumUpload({ onUpload }) {
  const [sourceMode, setSourceMode] = useState('file') // 'file' | 'url'
  const [tutorMode, setTutorMode] = useState('discovery')
  const [subject, setSubject] = useState('')
  const [file, setFile] = useState(null)
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const fileRef = useRef(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (!subject.trim()) { setError('Please enter a subject.'); return }

    setLoading(true)
    try {
      if (sourceMode === 'file') {
        if (!file) { setError('Please choose a file.'); setLoading(false); return }
        const form = new FormData()
        form.append('subject', subject.trim())
        form.append('file', file)
        form.append('mode', tutorMode)
        const res = await fetch(`${API}/curriculum/upload`, { method: 'POST', body: form })
        if (!res.ok) throw new Error('Upload failed')
        const data = await res.json()
        onUpload({ session_id: data.session_id, subject: subject.trim(), chunks_stored: data.chunks_stored, mode: data.mode })
      } else {
        if (!url.trim()) { setError('Please enter a URL.'); setLoading(false); return }
        const res = await fetch(`${API}/curriculum/upload-url`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ subject: subject.trim(), url: url.trim(), mode: tutorMode }),
        })
        if (!res.ok) throw new Error('Request failed')
        const data = await res.json()
        if (data.error) { setError(`Couldn't access that URL: ${data.error}`); return }
        onUpload({ session_id: data.session_id, subject: subject.trim(), chunks_stored: data.chunks_stored, mode: data.mode })
      }
    } catch {
      setError('Something went wrong. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  function handleDrop(e) {
    e.preventDefault()
    const dropped = e.dataTransfer.files[0]
    if (dropped) setFile(dropped)
  }

  return (
    <form className="cu-form" onSubmit={handleSubmit}>

      <div className="cu-field">
        <label className="cu-label">Subject</label>
        <input
          className="cu-input"
          type="text"
          placeholder="e.g. AP Biology, Chapter 4"
          value={subject}
          onChange={e => setSubject(e.target.value)}
          disabled={loading}
        />
      </div>

      {/* Tutor mode selector */}
      <div className="cu-field">
        <label className="cu-label">Tutor Style</label>
        <div className="cu-tutor-modes">
          {TUTOR_MODES.map(m => (
            <button
              key={m.key}
              type="button"
              className={`cu-tutor-mode-card ${tutorMode === m.key ? 'active' : ''}`}
              onClick={() => setTutorMode(m.key)}
              disabled={loading}
            >
              <span className="cu-tutor-mode-header">
                <span className="cu-tutor-mode-icon">{m.icon}</span>
                <span className="cu-tutor-mode-label">{m.label}</span>
                {tutorMode === m.key && <span className="cu-tutor-mode-check">✓</span>}
              </span>
              <span className="cu-tutor-mode-desc">{m.desc}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Source toggle */}
      <div className="cu-mode-toggle">
        <button
          type="button"
          className={`cu-mode-btn ${sourceMode === 'file' ? 'active' : ''}`}
          onClick={() => { setSourceMode('file'); setError('') }}
        >
          Upload File
        </button>
        <button
          type="button"
          className={`cu-mode-btn ${sourceMode === 'url' ? 'active' : ''}`}
          onClick={() => { setSourceMode('url'); setError('') }}
        >
          Paste Link
        </button>
      </div>

      {sourceMode === 'file' ? (
        <div className="cu-field">
          <label className="cu-label">Curriculum File (.txt or .pdf)</label>
          <div
            className={`cu-dropzone ${file ? 'has-file' : ''}`}
            onDragOver={e => e.preventDefault()}
            onDrop={handleDrop}
            onClick={() => fileRef.current?.click()}
          >
            {file ? (
              <>
                <span className="cu-file-icon">📄</span>
                <span className="cu-file-name">{file.name}</span>
                <span className="cu-file-size">({(file.size / 1024).toFixed(1)} KB)</span>
              </>
            ) : (
              <>
                <span className="cu-upload-icon">⬆</span>
                <span>Drop a .txt or .pdf here, or click to browse</span>
              </>
            )}
          </div>
          <input
            ref={fileRef}
            type="file"
            accept=".txt,.pdf,text/plain,application/pdf"
            style={{ display: 'none' }}
            onChange={e => setFile(e.target.files[0] || null)}
            disabled={loading}
          />
        </div>
      ) : (
        <div className="cu-field">
          <label className="cu-label">Curriculum URL</label>
          <input
            className="cu-input cu-url-input"
            type="url"
            placeholder="https://en.wikipedia.org/wiki/..."
            value={url}
            onChange={e => setUrl(e.target.value)}
            disabled={loading}
          />
          <p className="cu-url-hint">
            Works best with publicly accessible pages (Wikipedia, open textbooks, etc.).
            Pages behind a login or paywall will show an error.
          </p>
        </div>
      )}

      {error && <p className="cu-error">{error}</p>}

      <button className="cu-submit" type="submit" disabled={loading}>
        {loading
          ? (sourceMode === 'url' ? 'Fetching page…' : 'Uploading…')
          : 'Start Session'}
      </button>
    </form>
  )
}
