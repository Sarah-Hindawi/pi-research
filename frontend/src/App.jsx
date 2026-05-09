import { useState, useRef, useEffect } from 'react'
import { useChat } from './hooks/useChat'
import { getSessions, deleteSession, getStats } from './api/client'
import ReactMarkdown from 'react-markdown'

const SUGGESTED = [
  'What is the average verdict for a herniated disc from a rear-end collision in Ontario?',
  'Which neurosurgeons appear most often as plaintiff experts in Ontario spinal cases?',
  'Does a WAD II injury meet the Ontario Minor Injury Guideline threshold?',
  'What did similar rear-end MVA cases settle for in the last 3 years?',
]

export default function App() {
  const { messages, sessionId, loading, error, send, loadSession, newChat } = useChat()
  const [input, setInput] = useState('')
  const [sessions, setSessions] = useState([])
  const [stats, setStats] = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  // Load sessions + stats on mount
  useEffect(() => {
    getSessions().then(setSessions).catch(() => {})
    getStats().then(setStats).catch(() => {})
  }, [])

  // Refresh sessions list after each message
  useEffect(() => {
    if (sessionId) getSessions().then(setSessions).catch(() => {})
  }, [sessionId, messages.length])

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleSend = async (text) => {
    const q = (text || input).trim()
    if (!q || loading) return
    setInput('')
    await send(q)
    inputRef.current?.focus()
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleDeleteSession = async (id, e) => {
    e.stopPropagation()
    await deleteSession(id)
    setSessions(s => s.filter(x => x.session_id !== id))
    if (sessionId === id) newChat()
  }

  return (
    <div style={styles.shell}>
      {/* Sidebar */}
      {sidebarOpen && (
        <aside style={styles.sidebar}>
          <div style={styles.sidebarTop}>
            <span style={styles.logo}>⚖ OpenClaw</span>
            <button style={styles.iconBtn} onClick={() => setSidebarOpen(false)} title="Close sidebar">✕</button>
          </div>

          <button style={styles.newChatBtn} onClick={newChat}>+ New research</button>

          {stats && (
            <div style={styles.statPill}>
              {stats.cases_indexed.toLocaleString()} cases indexed
            </div>
          )}

          <div style={styles.sessionLabel}>Recent sessions</div>
          <div style={styles.sessionList}>
            {sessions.length === 0 && (
              <div style={styles.emptySession}>No sessions yet</div>
            )}
            {sessions.map(s => (
              <div
                key={s.session_id}
                style={{
                  ...styles.sessionItem,
                  ...(s.session_id === sessionId ? styles.sessionItemActive : {}),
                }}
                onClick={() => loadSession(s.session_id)}
              >
                <span style={styles.sessionTitle}>
                  {s.label || 'Research session'}
                </span>
                <span style={styles.sessionDate}>
                  {s.last_activity ? new Date(s.last_activity).toLocaleDateString() : ''}
                </span>
                <button
                  style={styles.deleteBtn}
                  onClick={(e) => handleDeleteSession(s.session_id, e)}
                  title="Delete"
                >✕</button>
              </div>
            ))}
          </div>

          <div style={styles.sidebarFooter}>
            <div style={styles.footerBadge}>
              LLM: {stats?.llm_provider === 'anthropic' ? '✓ Claude' : '⏳ Placeholder'}
            </div>
            <div style={styles.footerBadge}>Federal + Ontario</div>
          </div>
        </aside>
      )}

      {/* Main */}
      <div style={styles.main}>
        {/* Topbar */}
        <div style={styles.topbar}>
          {!sidebarOpen && (
            <button style={styles.iconBtn} onClick={() => setSidebarOpen(true)} title="Open sidebar">☰</button>
          )}
          <span style={styles.topbarTitle}>PI Legal Research</span>
          {sessionId && (
            <span style={styles.sessionBadge}>Session active</span>
          )}
        </div>

        {/* Messages */}
        <div style={styles.messages}>
          {messages.length === 0 && (
            <div style={styles.welcome}>
              <div style={styles.welcomeIcon}>⚖</div>
              <h2 style={styles.welcomeTitle}>Ask anything about PI case law</h2>
              <p style={styles.welcomeSub}>Federal + Ontario · Cited answers only</p>
              <div style={styles.suggestions}>
                {SUGGESTED.map((s, i) => (
                  <button key={i} style={styles.suggestionBtn} onClick={() => handleSend(s)}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} style={msg.role === 'user' ? styles.userBubbleWrap : styles.aiBubbleWrap}>
              {msg.role === 'user' ? (
                <div style={styles.userBubble}>{msg.content}</div>
              ) : (
                <div style={styles.aiBubble}>
                  {msg.intent && (
                    <div style={styles.intentTag}>{msg.intent}</div>
                  )}
                  <div style={styles.markdownBody}>
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  </div>
                  {msg.sources?.length > 0 && (
                    <div style={styles.sources}>
                      <div style={styles.sourcesLabel}>Sources</div>
                      {msg.sources.map((src, j) => (
                        <a
                          key={j}
                          href={src.url}
                          target="_blank"
                          rel="noreferrer"
                          style={styles.sourceLink}
                        >
                          <span style={styles.sourceName}>{src.case_name}</span>
                          <span style={styles.sourceMeta}>
                            {src.citation} · {src.jurisdiction} · {src.year}
                          </span>
                        </a>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div style={styles.aiBubbleWrap}>
              <div style={styles.aiBubble}>
                <div style={styles.thinking}>
                  <span style={styles.dot} />
                  <span style={styles.dot} />
                  <span style={styles.dot} />
                  <span style={styles.thinkingText}>Searching case law...</span>
                </div>
              </div>
            </div>
          )}

          {error && (
            <div style={styles.errorBanner}>⚠ {error}</div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div style={styles.inputArea}>
          <textarea
            ref={inputRef}
            style={styles.textarea}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Ask about verdicts, expert witnesses, thresholds, settlement ranges..."
            rows={2}
            disabled={loading}
          />
          <button
            style={{
              ...styles.sendBtn,
              opacity: (!input.trim() || loading) ? 0.4 : 1,
            }}
            onClick={() => handleSend()}
            disabled={!input.trim() || loading}
          >
            ↑
          </button>
        </div>
        <div style={styles.disclaimer}>
          All answers cite real CanLII sources. Verify before use in proceedings.
        </div>
      </div>
    </div>
  )
}

// ── Styles ─────────────────────────────────────────────────────────────────
const styles = {
  shell: {
    display: 'flex',
    height: '100vh',
    fontFamily: "'Georgia", 'serif',
    background: '#0f0f0f',
    color: '#e8e4d9',
  },
  sidebar: {
    width: 240,
    minWidth: 240,
    background: '#161616',
    borderRight: '1px solid #2a2a2a',
    display: 'flex',
    flexDirection: 'column',
    padding: '16px 12px',
    gap: 8,
  },
  sidebarTop: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  logo: {
    fontSize: 15,
    fontWeight: 600,
    color: '#c8b97a',
    letterSpacing: '0.02em',
  },
  iconBtn: {
    background: 'none',
    border: 'none',
    color: '#666',
    cursor: 'pointer',
    fontSize: 14,
    padding: '4px 6px',
    borderRadius: 4,
  },
  newChatBtn: {
    background: '#c8b97a',
    color: '#0f0f0f',
    border: 'none',
    borderRadius: 6,
    padding: '8px 12px',
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
    width: '100%',
    textAlign: 'left',
  },
  statPill: {
    fontSize: 11,
    color: '#555',
    padding: '4px 8px',
    background: '#1e1e1e',
    borderRadius: 4,
    textAlign: 'center',
  },
  sessionLabel: {
    fontSize: 10,
    color: '#444',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    padding: '8px 4px 4px',
  },
  sessionList: {
    flex: 1,
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
  },
  emptySession: {
    fontSize: 12,
    color: '#3a3a3a',
    padding: '8px 4px',
  },
  sessionItem: {
    padding: '8px 10px',
    borderRadius: 6,
    cursor: 'pointer',
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
    position: 'relative',
  },
  sessionItemActive: {
    background: '#1e1e1e',
    border: '1px solid #2a2a2a',
  },
  sessionTitle: {
    fontSize: 12,
    color: '#aaa',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    paddingRight: 16,
  },
  sessionDate: {
    fontSize: 10,
    color: '#444',
  },
  deleteBtn: {
    position: 'absolute',
    right: 6,
    top: 8,
    background: 'none',
    border: 'none',
    color: '#444',
    cursor: 'pointer',
    fontSize: 11,
    padding: 2,
  },
  sidebarFooter: {
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
    borderTop: '1px solid #2a2a2a',
    paddingTop: 12,
  },
  footerBadge: {
    fontSize: 10,
    color: '#444',
    padding: '3px 6px',
  },
  main: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    minWidth: 0,
  },
  topbar: {
    padding: '12px 20px',
    borderBottom: '1px solid #2a2a2a',
    display: 'flex',
    alignItems: 'center',
    gap: 12,
  },
  topbarTitle: {
    fontSize: 14,
    color: '#666',
    flex: 1,
  },
  sessionBadge: {
    fontSize: 10,
    background: '#1e2e1e',
    color: '#4a8c4a',
    padding: '3px 8px',
    borderRadius: 10,
    border: '1px solid #2a4a2a',
  },
  messages: {
    flex: 1,
    overflowY: 'auto',
    padding: '24px 20px',
    display: 'flex',
    flexDirection: 'column',
    gap: 20,
    maxWidth: 760,
    width: '100%',
    margin: '0 auto',
    alignSelf: 'center',
    boxSizing: 'border-box',
  },
  welcome: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 12,
    padding: '40px 0',
    textAlign: 'center',
  },
  welcomeIcon: {
    fontSize: 40,
  },
  welcomeTitle: {
    fontSize: 22,
    fontWeight: 400,
    color: '#e8e4d9',
    margin: 0,
  },
  welcomeSub: {
    fontSize: 13,
    color: '#555',
    margin: 0,
  },
  suggestions: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    marginTop: 16,
    width: '100%',
    maxWidth: 560,
  },
  suggestionBtn: {
    background: '#161616',
    border: '1px solid #2a2a2a',
    borderRadius: 8,
    color: '#888',
    fontSize: 13,
    padding: '10px 14px',
    cursor: 'pointer',
    textAlign: 'left',
    lineHeight: 1.4,
    transition: 'border-color 0.15s',
  },
  userBubbleWrap: {
    display: 'flex',
    justifyContent: 'flex-end',
  },
  userBubble: {
    background: '#1e1e1e',
    border: '1px solid #2a2a2a',
    borderRadius: '12px 12px 2px 12px',
    padding: '10px 14px',
    fontSize: 14,
    color: '#e8e4d9',
    maxWidth: '80%',
    lineHeight: 1.5,
  },
  aiBubbleWrap: {
    display: 'flex',
    justifyContent: 'flex-start',
  },
  aiBubble: {
    maxWidth: '100%',
    width: '100%',
  },
  intentTag: {
    display: 'inline-block',
    fontSize: 10,
    color: '#c8b97a',
    background: '#1e1a0e',
    border: '1px solid #3a3018',
    borderRadius: 4,
    padding: '2px 7px',
    marginBottom: 8,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
  },
  markdownBody: {
    fontSize: 14,
    lineHeight: 1.7,
    color: '#ccc',
  },
  sources: {
    marginTop: 16,
    borderTop: '1px solid #2a2a2a',
    paddingTop: 12,
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
  },
  sourcesLabel: {
    fontSize: 10,
    color: '#444',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    marginBottom: 4,
  },
  sourceLink: {
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
    padding: '6px 10px',
    background: '#161616',
    border: '1px solid #2a2a2a',
    borderRadius: 6,
    textDecoration: 'none',
    transition: 'border-color 0.15s',
  },
  sourceName: {
    fontSize: 12,
    color: '#c8b97a',
  },
  sourceMeta: {
    fontSize: 10,
    color: '#555',
  },
  thinking: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: '50%',
    background: '#c8b97a',
    animation: 'pulse 1.2s ease-in-out infinite',
  },
  thinkingText: {
    fontSize: 12,
    color: '#555',
    marginLeft: 4,
  },
  errorBanner: {
    background: '#2a1a1a',
    border: '1px solid #4a2a2a',
    color: '#c87a7a',
    padding: '10px 14px',
    borderRadius: 8,
    fontSize: 13,
  },
  inputArea: {
    display: 'flex',
    alignItems: 'flex-end',
    gap: 8,
    padding: '12px 20px',
    borderTop: '1px solid #2a2a2a',
    maxWidth: 760,
    width: '100%',
    margin: '0 auto',
    alignSelf: 'center',
    boxSizing: 'border-box',
  },
  textarea: {
    flex: 1,
    background: '#161616',
    border: '1px solid #2a2a2a',
    borderRadius: 8,
    color: '#e8e4d9',
    fontSize: 14,
    padding: '10px 14px',
    resize: 'none',
    fontFamily: 'inherit',
    lineHeight: 1.5,
    outline: 'none',
  },
  sendBtn: {
    background: '#c8b97a',
    color: '#0f0f0f',
    border: 'none',
    borderRadius: 8,
    width: 40,
    height: 40,
    fontSize: 18,
    cursor: 'pointer',
    fontWeight: 700,
    flexShrink: 0,
  },
  disclaimer: {
    fontSize: 10,
    color: '#333',
    textAlign: 'center',
    padding: '6px 0 10px',
  },
}
