import { useState, useRef, useEffect } from 'react'
import { useChat } from './hooks/useChat'
import { getSessions, deleteSession, getStats } from './api/client'
import ReactMarkdown from 'react-markdown'

const SUGGESTED = [
  'What is the California statute for driving under the influence?',
  'Show me all DUI/DWI statutes across all states',
  'Compare failure to yield laws between California and Texas',
  'What statutes cover reckless driving in Florida?',
  'Find all statutes related to using a phone while driving',
]

export default function App() {
  const { messages, sessionId, loading, error, send, loadSession, newChat } = useChat()
  const [input, setInput] = useState('')
  const [sessions, setSessions] = useState([])
  const [stats, setStats] = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    getSessions().then(setSessions).catch(() => {})
    getStats().then(setStats).catch(() => {})
  }, [])

  useEffect(() => {
    if (sessionId) getSessions().then(setSessions).catch(() => {})
  }, [sessionId, messages.length])

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

  const handleDelete = async (id, e) => {
    e.stopPropagation()
    await deleteSession(id)
    setSessions(s => s.filter(x => x.session_id !== id))
    if (sessionId === id) newChat()
  }

  return (
    <div style={s.shell}>
      {sidebarOpen && (
        <aside style={s.sidebar}>
          <div style={s.sidebarTop}>
            <span style={s.logo}>⚖ OpenClaw</span>
            <button style={s.iconBtn} onClick={() => setSidebarOpen(false)}>✕</button>
          </div>

          <button style={s.newChatBtn} onClick={newChat}>+ New research</button>

          {stats && (
            <div style={s.statsBlock}>
              <div style={s.statRow}>
                <span style={s.statVal}>{stats.statutes_indexed?.toLocaleString() ?? 0}</span>
                <span style={s.statLbl}>statutes indexed</span>
              </div>
              <div style={s.statRow}>
                <span style={s.statVal}>{stats.states?.length ?? 0}</span>
                <span style={s.statLbl}>states</span>
              </div>
            </div>
          )}

          {stats?.states?.length > 0 && (
            <>
              <div style={s.sectionLabel}>States</div>
              <div style={s.tagList}>
                {stats.states.map(st => (
                  <span key={st} style={s.tag}>{st}</span>
                ))}
              </div>
            </>
          )}

          <div style={s.sectionLabel}>Recent sessions</div>
          <div style={s.sessionList}>
            {sessions.length === 0 && <div style={s.empty}>No sessions yet</div>}
            {sessions.map(sess => (
              <div
                key={sess.session_id}
                style={{ ...s.sessionItem, ...(sess.session_id === sessionId ? s.sessionActive : {}) }}
                onClick={() => loadSession(sess.session_id)}
              >
                <span style={s.sessionTitle}>{sess.label || 'Research session'}</span>
                <span style={s.sessionDate}>
                  {sess.last_activity ? new Date(sess.last_activity).toLocaleDateString() : ''}
                </span>
                <button style={s.delBtn} onClick={(e) => handleDelete(sess.session_id, e)}>✕</button>
              </div>
            ))}
          </div>

          <div style={s.footer}>
            <span style={s.footerBadge}>
              {stats?.llm_provider === 'anthropic' ? '✓ Claude connected' : '⏳ Placeholder LLM'}
            </span>
          </div>
        </aside>
      )}

      <div style={s.main}>
        <div style={s.topbar}>
          {!sidebarOpen && (
            <button style={s.iconBtn} onClick={() => setSidebarOpen(true)}>☰</button>
          )}
          <span style={s.topbarTitle}>US Vehicle Code Research</span>
          {sessionId && <span style={s.activeBadge}>Session active</span>}
        </div>

        <div style={s.messages}>
          {messages.length === 0 && (
            <div style={s.welcome}>
              <div style={s.welcomeIcon}>⚖</div>
              <h2 style={s.welcomeTitle}>US Vehicle Code Harvester</h2>
              <p style={s.welcomeSub}>Search statutes by contributing factor, citation, or state</p>
              <div style={s.suggestions}>
                {SUGGESTED.map((q, i) => (
                  <button key={i} style={s.suggestion} onClick={() => handleSend(q)}>{q}</button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} style={msg.role === 'user' ? s.userWrap : s.aiWrap}>
              {msg.role === 'user' ? (
                <div style={s.userBubble}>{msg.content}</div>
              ) : (
                <div style={s.aiBubble}>
                  {msg.intent && (
                    <div style={s.intentRow}>
                      <span style={s.intentTag}>{msg.intent.replace('_', ' ')}</span>
                      {msg.filters?.state && <span style={s.filterTag}>{msg.filters.state}</span>}
                      {msg.filters?.factor && <span style={s.filterTag}>{msg.filters.factor}</span>}
                    </div>
                  )}
                  <div style={s.mdBody}>
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  </div>
                  {msg.sources?.length > 0 && (
                    <div style={s.sources}>
                      <div style={s.sourcesLabel}>Sources ({msg.sources.length})</div>
                      {msg.sources.map((src, j) => (
                        <a key={j} href={src.source_url} target="_blank" rel="noreferrer" style={s.sourceCard}>
                          <div style={s.sourceCitation}>{src.statute}</div>
                          <div style={s.sourceMeta}>
                            {src.state} · {src.contributing_factor}
                          </div>
                        </a>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div style={s.aiWrap}>
              <div style={s.aiBubble}>
                <div style={s.thinking}>
                  <span style={s.dot} /><span style={s.dot} /><span style={s.dot} />
                  <span style={s.thinkingText}>Searching statutes...</span>
                </div>
              </div>
            </div>
          )}

          {error && <div style={s.error}>⚠ {error}</div>}
          <div ref={bottomRef} />
        </div>

        <div style={s.inputArea}>
          <textarea
            ref={inputRef}
            style={s.textarea}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="e.g. 'Show me all DUI statutes in Texas' or 'Cal. Veh. Code § 22350'"
            rows={2}
            disabled={loading}
          />
          <button
            style={{ ...s.sendBtn, opacity: (!input.trim() || loading) ? 0.4 : 1 }}
            onClick={() => handleSend()}
            disabled={!input.trim() || loading}
          >↑</button>
        </div>
        <div style={s.disclaimer}>
          All statutes cite real source URLs. Verify before use in proceedings.
        </div>
      </div>
    </div>
  )
}

const s = {
  shell: { display: 'flex', height: '100vh', fontFamily: 'Georgia, serif', background: '#0f0f0f', color: '#e8e4d9' },
  sidebar: { width: 240, minWidth: 240, background: '#161616', borderRight: '1px solid #2a2a2a', display: 'flex', flexDirection: 'column', padding: '16px 12px', gap: 8 },
  sidebarTop: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
  logo: { fontSize: 15, fontWeight: 600, color: '#c8b97a', letterSpacing: '0.02em' },
  iconBtn: { background: 'none', border: 'none', color: '#666', cursor: 'pointer', fontSize: 14, padding: '4px 6px', borderRadius: 4 },
  newChatBtn: { background: '#c8b97a', color: '#0f0f0f', border: 'none', borderRadius: 6, padding: '8px 12px', fontSize: 13, fontWeight: 600, cursor: 'pointer', width: '100%', textAlign: 'left' },
  statsBlock: { background: '#1e1e1e', borderRadius: 6, padding: '8px 10px', display: 'flex', gap: 12 },
  statRow: { display: 'flex', flexDirection: 'column', gap: 2 },
  statVal: { fontSize: 18, fontWeight: 600, color: '#c8b97a' },
  statLbl: { fontSize: 10, color: '#555' },
  sectionLabel: { fontSize: 10, color: '#444', textTransform: 'uppercase', letterSpacing: '0.08em', padding: '8px 4px 4px' },
  tagList: { display: 'flex', flexWrap: 'wrap', gap: 4, padding: '0 2px' },
  tag: { fontSize: 10, background: '#1e1e1e', color: '#888', border: '1px solid #2a2a2a', borderRadius: 4, padding: '2px 6px' },
  sessionList: { flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 2 },
  empty: { fontSize: 12, color: '#3a3a3a', padding: '8px 4px' },
  sessionItem: { padding: '8px 10px', borderRadius: 6, cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: 2, position: 'relative' },
  sessionActive: { background: '#1e1e1e', border: '1px solid #2a2a2a' },
  sessionTitle: { fontSize: 12, color: '#aaa', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', paddingRight: 16 },
  sessionDate: { fontSize: 10, color: '#444' },
  delBtn: { position: 'absolute', right: 6, top: 8, background: 'none', border: 'none', color: '#444', cursor: 'pointer', fontSize: 11 },
  footer: { borderTop: '1px solid #2a2a2a', paddingTop: 10 },
  footerBadge: { fontSize: 10, color: '#555' },
  main: { flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 },
  topbar: { padding: '12px 20px', borderBottom: '1px solid #2a2a2a', display: 'flex', alignItems: 'center', gap: 12 },
  topbarTitle: { fontSize: 14, color: '#666', flex: 1 },
  activeBadge: { fontSize: 10, background: '#1e2e1e', color: '#4a8c4a', padding: '3px 8px', borderRadius: 10, border: '1px solid #2a4a2a' },
  messages: { flex: 1, overflowY: 'auto', padding: '24px 20px', display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 760, width: '100%', margin: '0 auto', alignSelf: 'center', boxSizing: 'border-box' },
  welcome: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, padding: '40px 0', textAlign: 'center' },
  welcomeIcon: { fontSize: 40 },
  welcomeTitle: { fontSize: 22, fontWeight: 400, color: '#e8e4d9', margin: 0 },
  welcomeSub: { fontSize: 13, color: '#555', margin: 0 },
  suggestions: { display: 'flex', flexDirection: 'column', gap: 8, marginTop: 16, width: '100%', maxWidth: 580 },
  suggestion: { background: '#161616', border: '1px solid #2a2a2a', borderRadius: 8, color: '#888', fontSize: 13, padding: '10px 14px', cursor: 'pointer', textAlign: 'left', lineHeight: 1.4 },
  userWrap: { display: 'flex', justifyContent: 'flex-end' },
  userBubble: { background: '#1e1e1e', border: '1px solid #2a2a2a', borderRadius: '12px 12px 2px 12px', padding: '10px 14px', fontSize: 14, color: '#e8e4d9', maxWidth: '80%', lineHeight: 1.5 },
  aiWrap: { display: 'flex', justifyContent: 'flex-start' },
  aiBubble: { maxWidth: '100%', width: '100%' },
  intentRow: { display: 'flex', gap: 6, marginBottom: 8, flexWrap: 'wrap' },
  intentTag: { fontSize: 10, color: '#c8b97a', background: '#1e1a0e', border: '1px solid #3a3018', borderRadius: 4, padding: '2px 7px', textTransform: 'uppercase', letterSpacing: '0.06em' },
  filterTag: { fontSize: 10, color: '#7a9cc8', background: '#0e141e', border: '1px solid #183058', borderRadius: 4, padding: '2px 7px' },
  mdBody: { fontSize: 14, lineHeight: 1.7, color: '#ccc' },
  sources: { marginTop: 16, borderTop: '1px solid #2a2a2a', paddingTop: 12, display: 'flex', flexDirection: 'column', gap: 6 },
  sourcesLabel: { fontSize: 10, color: '#444', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 },
  sourceCard: { display: 'flex', flexDirection: 'column', gap: 2, padding: '6px 10px', background: '#161616', border: '1px solid #2a2a2a', borderRadius: 6, textDecoration: 'none' },
  sourceCitation: { fontSize: 12, color: '#c8b97a' },
  sourceMeta: { fontSize: 10, color: '#555' },
  thinking: { display: 'flex', alignItems: 'center', gap: 6 },
  dot: { width: 6, height: 6, borderRadius: '50%', background: '#c8b97a' },
  thinkingText: { fontSize: 12, color: '#555', marginLeft: 4 },
  error: { background: '#2a1a1a', border: '1px solid #4a2a2a', color: '#c87a7a', padding: '10px 14px', borderRadius: 8, fontSize: 13 },
  inputArea: { display: 'flex', alignItems: 'flex-end', gap: 8, padding: '12px 20px', borderTop: '1px solid #2a2a2a', maxWidth: 760, width: '100%', margin: '0 auto', alignSelf: 'center', boxSizing: 'border-box' },
  textarea: { flex: 1, background: '#161616', border: '1px solid #2a2a2a', borderRadius: 8, color: '#e8e4d9', fontSize: 14, padding: '10px 14px', resize: 'none', fontFamily: 'inherit', lineHeight: 1.5, outline: 'none' },
  sendBtn: { background: '#c8b97a', color: '#0f0f0f', border: 'none', borderRadius: 8, width: 40, height: 40, fontSize: 18, cursor: 'pointer', fontWeight: 700, flexShrink: 0 },
  disclaimer: { fontSize: 10, color: '#333', textAlign: 'center', padding: '6px 0 10px' },
}
