import { useState, useRef, useEffect } from 'react'
import './ChatWindow.css'

function renderContent(text) {
  // Bold **text** and line breaks
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br />')
}

export default function ChatWindow({ messages, onSend, thinking }) {
  const [input, setInput] = useState('')
  const bottomRef = useRef(null)
  const textareaRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, thinking])

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  function handleSend() {
    const text = input.trim()
    if (!text || thinking) return
    setInput('')
    onSend(text)
    setTimeout(() => textareaRef.current?.focus(), 0)
  }

  return (
    <div className="cw-root">
      <div className="cw-messages">
        {messages.map((m, i) => (
          <div key={i} className={`cw-bubble-row ${m.role}`}>
            <div
              className={`cw-bubble ${m.role} ${m.blocked ? 'blocked' : ''} ${m.error ? 'error' : ''}`}
              dangerouslySetInnerHTML={{ __html: renderContent(m.content) }}
            />
          </div>
        ))}
        {thinking && (
          <div className="cw-bubble-row assistant">
            <div className="cw-bubble assistant thinking">
              <span className="cw-dot" />
              <span className="cw-dot" />
              <span className="cw-dot" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <div className="cw-input-bar">
        <textarea
          ref={textareaRef}
          className="cw-textarea"
          rows={2}
          placeholder="Ask about your curriculum… (Enter to send, Shift+Enter for newline)"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={thinking}
        />
        <button
          className="cw-send-btn"
          onClick={handleSend}
          disabled={thinking || !input.trim()}
        >
          Send
        </button>
      </div>
    </div>
  )
}
