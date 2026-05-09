import { useState, useRef, useEffect } from 'react'
import { useChat } from './hooks/useChat'
import { getSessions, deleteSession, getStats } from './api/client'
import ReactMarkdown from 'react-markdown'

// ── Constants ──────────────────────────────────────────────────────────────
const EXAMPLE_PROMPTS = [
  { label: 'CA texting driver rear-end', text: 'California rear-end with texting driver' },
  { label: 'Cal. Veh. § 23123.5',        text: 'Cal. Veh. Code § 23123.5' },
  { label: 'DUI statutes across states', text: 'DUI statutes across states' },
  { label: 'Failure to yield Florida',   text: 'What statutes cover failure to yield in Florida?' },
  { label: 'Reckless driving Texas',     text: 'Reckless driving statutes in Texas' },
]

// Tabs that show locked state (no real data yet from backend)
const LOCKED_TABS = new Set(['caselaw', 'multistate'])

// ── Icons ──────────────────────────────────────────────────────────────────
function ChevronIcon({ open }) {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none"
      className={`text-primary-tertiary transition-transform ${open ? 'rotate-180' : ''}`}>
      <path d="M3 5 L7 9 L11 5" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" />
    </svg>
  )
}

function TrashIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
      <path d="M1.5 3h9M4.5 3V2a.5.5 0 0 1 .5-.5h2a.5.5 0 0 1 .5.5v1M10 3l-.7 7a.5.5 0 0 1-.5.5H3.2a.5.5 0 0 1-.5-.5L2 3"
        stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" />
    </svg>
  )
}

function LockIcon({ className = '' }) {
  return (
    <svg className={className} viewBox="0 0 12 12" fill="none">
      <rect x="2.5" y="5.5" width="7" height="5" rx="1" stroke="currentColor" strokeWidth="1.2" />
      <path d="M4 5.5V4 a 2 2 0 0 1 4 0 V5.5" stroke="currentColor" strokeWidth="1.2" fill="none" />
    </svg>
  )
}

// ── Shared components ──────────────────────────────────────────────────────

function Field({ label, value }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] text-primary-tertiary tracking-wider uppercase font-semibold">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  )
}

// ConfidenceBadge — dual mode:
//   level prop  → "high"/"medium"/"low" (case understanding)
//   score+verdict props → 0-1 float + pass/partial/fail (eval judge)
function ConfidenceBadge({ level, score, verdict, details }) {
  if (level) {
    const dots  = level === 'high' ? 4 : level === 'medium' ? 3 : 2
    const color = level === 'low' ? 'text-warning' : 'text-success'
    const bg    = level === 'low' ? 'bg-warning'   : 'bg-success'
    return (
      <span className={`inline-flex items-center gap-1.5 text-xs font-semibold ${color}`}>
        <span className="inline-flex gap-1">
          {Array.from({ length: 4 }).map((_, i) => (
            <span key={i} className={`w-2 h-2 rounded-full ${i < dots ? bg : 'bg-border-soft'}`} />
          ))}
        </span>
        Confidence: {level[0].toUpperCase() + level.slice(1)}
      </span>
    )
  }
  if (score !== undefined) {
    const pct      = Math.round(score * 100)
    const dots     = verdict === 'pass' ? 4 : verdict === 'partial' ? 2 : 1
    const color    = verdict === 'pass'    ? 'text-success border-success bg-success-soft'
                   : verdict === 'partial' ? 'text-warning border-warning bg-warning-soft'
                   :                         'text-red-700 border-red-200 bg-red-50'
    const dotColor = verdict === 'pass'    ? 'bg-success'
                   : verdict === 'partial' ? 'bg-warning'
                   :                         'bg-red-500'
    return (
      <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border text-[11px] font-semibold ${color} mb-3`}>
        <span className="inline-flex gap-0.5">
          {Array.from({ length: 4 }).map((_, i) => (
            <span key={i} className={`w-1.5 h-1.5 rounded-full ${i < dots ? dotColor : 'opacity-20 ' + dotColor}`} />
          ))}
        </span>
        {pct}% confidence · {verdict}
        {details && (
          <span className="opacity-60 font-normal ml-1">
            C:{Math.round((details.correctness  ?? 0) * 100)}%{' '}
            F:{Math.round((details.faithfulness ?? 0) * 100)}%{' '}
            R:{Math.round((details.relevance    ?? 0) * 100)}%
          </span>
        )}
      </div>
    )
  }
  return null
}

function FactorStrength({ strength }) {
  const filled = strength === 'strong' ? 4 : strength === 'likely' ? 3 : 2
  return (
    <span className="inline-flex items-center gap-2">
      <span className="inline-flex gap-1">
        {Array.from({ length: 4 }).map((_, i) => (
          <span key={i} className={`w-1.5 h-1.5 rounded-full ${i < filled ? 'bg-accent-navy' : 'bg-accent-blue-mid opacity-40'}`} />
        ))}
      </span>
      <span className="text-[11px] text-primary-secondary font-medium uppercase tracking-wide">{strength}</span>
    </span>
  )
}

function AccordionSection({ title, subtitle, count, tone = 'default', isOpen, onToggle, children }) {
  const indicator = tone === 'warning' ? 'bg-warning' : 'bg-accent-navy'
  const countBg   = tone === 'warning' ? 'bg-warning-soft text-warning' : 'bg-accent-blue-soft text-accent-navy'
  return (
    <div className="bg-card rounded-xl shadow-card mb-2.5 overflow-hidden">
      <button onClick={onToggle} className="w-full flex items-center justify-between gap-3 px-5 py-4 hover:bg-bg/50 transition-colors text-left">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className={`w-1 h-4 rounded-sm ${indicator} flex-shrink-0`} />
          <div className="min-w-0">
            <div className="font-serif text-[14px] font-bold text-primary truncate">{title}</div>
            {!isOpen && <div className="text-[11px] text-primary-tertiary mt-0.5 truncate">{subtitle}</div>}
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className={`${countBg} text-[11px] px-2 py-0.5 rounded-full font-semibold`}>{count}</span>
          <ChevronIcon open={isOpen} />
        </div>
      </button>
      {isOpen && (
        <div className="px-5 pb-5 pt-1">
          <div className="text-[11px] text-primary-tertiary mb-3">{subtitle}</div>
          {children}
        </div>
      )}
    </div>
  )
}

// ── Tab content components (from workplace design) ─────────────────────────

function LoadingState() {
  return (
    <div className="flex flex-col items-center justify-center py-20">
      <div className="text-sm text-primary-secondary">Workplace is searching…</div>
      <div className="mt-2 text-xs text-primary-tertiary">Querying statute database and reasoning over results</div>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="font-serif text-lg text-primary-secondary mb-2">Paste a case, citation, or category to get started</div>
      <div className="text-xs text-primary-tertiary">Use the example prompts in the left panel for ideas.</div>
    </div>
  )
}

function LockedFeature({ feature }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-12 h-12 rounded-full bg-accent-blue-soft flex items-center justify-center mb-4">
        <LockIcon className="w-5 h-5 text-accent-navy" />
      </div>
      <div className="font-serif text-lg text-primary mb-2">{feature}</div>
      <div className="text-xs text-primary-tertiary mb-4 max-w-[300px] leading-relaxed">
        Available in the Pro tier. Upgrade to unlock cross-jurisdictional analysis and case-law mapping
        powered by the same Workplace Harvester.
      </div>
      <button className="px-5 py-2 bg-accent-navy text-white rounded-lg text-[13px] font-semibold hover:bg-accent-blue transition-colors">
        Upgrade to unlock
      </button>
    </div>
  )
}

// Overview tab — case understanding + contributing factors
function OverviewTab({ messages }) {
  // Build analysis from the latest assistant message
  const latestMsg = [...messages].reverse().find(m => m.role === 'assistant')
  if (!latestMsg) return <EmptyState />

  const sources = latestMsg.sources || []
  const factors = [...new Map(sources.map(s => [s.contributing_factor, s])).values()]

  return (
    <div>
      {/* Intent card */}
      <div className="bg-bg rounded-xl p-6 mb-4">
        <div className="flex items-baseline justify-between mb-4">
          <div className="font-serif text-base font-bold">Query Analysis</div>
          {latestMsg.confidence && (
            <ConfidenceBadge
              score={latestMsg.confidence.overall}
              verdict={latestMsg.confidence.verdict}
            />
          )}
        </div>
        <div className="grid grid-cols-2 gap-x-7 gap-y-3.5">
          {latestMsg.intent && <Field label="Intent" value={latestMsg.intent.replace('_', ' ')} />}
          {latestMsg.filters?.state  && <Field label="State"  value={latestMsg.filters.state} />}
          {latestMsg.filters?.factor && <Field label="Factor" value={latestMsg.filters.factor} />}
          <Field label="Sources found" value={`${sources.length} statute${sources.length !== 1 ? 's' : ''}`} />
        </div>
      </div>

      {/* Contributing factors */}
      {factors.length > 0 && (
        <div className="bg-bg rounded-xl p-6">
          <div className="font-serif text-base font-bold mb-3.5">Contributing Factors</div>
          <div className="flex flex-col gap-2.5">
            {factors.map((f, i) => (
              <div key={i} className="flex items-center justify-between gap-3.5 p-3 bg-card rounded-lg border border-border-faint">
                <span className="text-sm font-medium">{f.contributing_factor}</span>
                <FactorStrength strength="strong" />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// Statutes tab — shows sources from last assistant message as statute cards
function StatutesTab({ messages }) {
  const latestMsg = [...messages].reverse().find(m => m.role === 'assistant')
  const sources = latestMsg?.sources || []

  if (!sources.length) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="font-serif text-lg text-primary-secondary mb-2">No statutes yet</div>
        <div className="text-xs text-primary-tertiary">Run a search to see relevant statutes here.</div>
      </div>
    )
  }

  return (
    <div>
      {sources.map((s, i) => (
        <div key={i} className="bg-bg rounded-xl p-5 mb-3 last:mb-0">
          <div className="flex justify-between items-baseline mb-2.5">
            <div className="font-serif text-[15px] font-bold">{s.statute}</div>
            <div className="text-[11px] text-primary-tertiary font-medium">{s.state}</div>
          </div>
          <div className="flex items-center gap-2.5 flex-wrap">
            <span className="bg-accent-navy text-white px-2.5 py-1 rounded-full text-[11px] font-semibold">
              {s.contributing_factor}
            </span>
            <span className="bg-bg text-primary-secondary border border-border-soft px-2.5 py-1 rounded-full text-[11px] font-semibold">
              {s.section}
            </span>
            <a
              href={s.source_url}
              target="_blank"
              rel="noreferrer"
              className="ml-auto text-xs text-accent-blue font-medium hover:underline"
            >
              View source ↗
            </a>
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Evidence / Gaps / Actions content (from workplace design) ──────────────

function EvidenceContent({ items }) {
  const groups = { high: [], medium: [], low: [] }
  items.forEach(it => groups[it.priority]?.push(it))
  return (
    <div>
      {['high', 'medium', 'low'].map(p => groups[p].length === 0 ? null : (
        <div key={p} className="mb-3 last:mb-0">
          <div className="inline-flex items-center gap-1 text-[10.5px] text-primary-secondary font-bold tracking-wider uppercase mb-1.5">
            <span className="text-warning tracking-widest">{p === 'high' ? '***' : p === 'medium' ? '**' : '*'}</span>
            {p} priority
          </div>
          {groups[p].map((e, i) => (
            <div key={i} className={`pl-3.5 py-2 mb-1.5 last:mb-0 text-[13px] text-primary border-l-2 ${p === 'high' ? 'border-warning' : p === 'medium' ? 'border-accent-blue' : 'border-border-soft'}`}>
              {e.evidence_type}
              <div className="text-[11.5px] text-primary-tertiary italic mt-0.5">{e.rationale}</div>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}

function GapsContent({ items }) {
  return (
    <div>
      {items.map((g, i) => (
        <div key={i} className="flex gap-2.5 px-3 py-2.5 bg-warning-soft rounded-lg mb-2 last:mb-0 text-[12.5px] leading-relaxed">
          <div className="w-1.5 h-1.5 rounded-full bg-warning mt-1.5 flex-shrink-0" />
          <div>
            <div className="text-primary">{g.description}</div>
            {g.verifiable_basis && (
              <div className="text-[11px] text-primary-tertiary mt-1 italic">{g.verifiable_basis}</div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

function ActionsContent({ items }) {
  return (
    <ol className="space-y-0">
      {items.map((a, i) => (
        <li key={i} className={`pl-7 py-2.5 text-[13px] leading-relaxed relative ${i < items.length - 1 ? 'border-b border-border-faint' : ''}`}>
          <span className="absolute left-0 top-3 w-5 h-5 bg-accent-navy text-white rounded-full flex items-center justify-center text-[11px] font-bold font-serif">
            {i + 1}
          </span>
          {a.action}
          <div className="text-[11.5px] text-primary-tertiary mt-0.5">{a.rationale}</div>
        </li>
      ))}
    </ol>
  )
}

// ── Top Nav ────────────────────────────────────────────────────────────────
function TopNav({ stats, onNewChat }) {
  return (
    <nav className="flex items-center justify-between px-8 py-5 border-b border-border-faint">
      <div className="flex items-baseline gap-4">
        <div className="font-serif text-2xl font-bold tracking-tight text-primary">Workplace</div>
        <div className="text-xs text-primary-tertiary tracking-wide">Legal Research for PI Attorneys</div>
      </div>
      <div className="flex items-center gap-4">
        {stats && (
          <div className="flex items-center gap-3 text-xs text-primary-tertiary">
            <span className="font-semibold text-accent-navy">{stats.statutes_indexed?.toLocaleString()}</span> statutes
            <span className="text-border-soft">·</span>
            <span className="font-semibold text-accent-navy">{stats.states?.length}</span> states
            <span className="text-border-soft">·</span>
            <span className={stats.llm_provider === 'anthropic' ? 'text-success font-semibold' : 'text-warning font-semibold'}>
              {stats.llm_provider === 'anthropic' ? '✓ Claude' : '⏳ Placeholder'}
            </span>
          </div>
        )}
        <button
          onClick={onNewChat}
          className="px-4 py-2 text-sm font-semibold bg-accent-navy text-white rounded-lg hover:bg-accent-blue transition-colors"
        >
          + New Research
        </button>
      </div>
    </nav>
  )
}

// ── Left Panel — Input + Sessions ─────────────────────────────────────────
function LeftPanel({ input, setInput, onSend, loading, onExample, sessions, sessionId, onLoadSession, onDeleteSession }) {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <div className="text-xs uppercase tracking-widest text-primary-tertiary font-semibold mb-3 pl-1">New Research</div>
        <div className="bg-card rounded-2xl p-6 shadow-card">
          <p className="text-[13px] text-primary-secondary mb-4 leading-relaxed">
            Describe a case, paste a citation, or look up a violation category.
          </p>
          <textarea
            className="w-full min-h-[180px] p-4 border border-border-soft rounded-xl bg-bg text-[14px] text-primary leading-relaxed resize-y focus:outline-none focus:border-accent-blue focus:bg-card transition-colors placeholder:text-primary-tertiary"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSend() } }}
            placeholder="Try: 'California rear-end with a texting driver', or paste 'Cal. Veh. Code § 23123.5', or look up 'DUI statutes across states'."
            disabled={loading}
          />
          <div className="mt-3">
            <div className="text-[11px] uppercase tracking-wide text-primary-tertiary font-semibold mb-2">Sample prompts</div>
            <div className="flex flex-wrap gap-1.5">
              {EXAMPLE_PROMPTS.map(ex => (
                <button
                  key={ex.label}
                  onClick={() => onExample(ex.text)}
                  className="px-2.5 py-1.5 bg-bg border border-border-soft rounded-full text-[12px] text-primary-secondary hover:border-accent-blue hover:text-accent-navy hover:bg-accent-blue-soft transition-all"
                >
                  {ex.label}
                </button>
              ))}
            </div>
          </div>
          <button
            onClick={onSend}
            disabled={loading || !input.trim()}
            className="w-full mt-5 py-3 bg-accent-navy text-white rounded-xl text-sm font-semibold hover:bg-accent-blue transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {loading ? 'Searching…' : 'Search'}
          </button>
        </div>
      </div>

      <div>
        <div className="text-xs uppercase tracking-widest text-primary-tertiary font-semibold mb-3 pl-1">Recent Sessions</div>
        <div className="bg-card rounded-2xl shadow-card overflow-hidden">
          {sessions.length === 0 ? (
            <div className="p-6 text-[13px] text-primary-tertiary text-center">No sessions yet</div>
          ) : (
            sessions.map(sess => (
              <div
                key={sess.session_id}
                onClick={() => onLoadSession(sess.session_id)}
                className={`flex items-center justify-between px-5 py-3.5 cursor-pointer border-b border-border-faint last:border-0 hover:bg-bg transition-colors group ${sess.session_id === sessionId ? 'bg-accent-blue-soft' : ''}`}
              >
                <div className="min-w-0">
                  <div className="text-[13px] text-primary truncate font-medium">{sess.label || 'Research session'}</div>
                  <div className="text-[11px] text-primary-tertiary mt-0.5">
                    {sess.last_activity ? new Date(sess.last_activity).toLocaleDateString() : ''}
                  </div>
                </div>
                <button
                  onClick={e => onDeleteSession(sess.session_id, e)}
                  className="opacity-0 group-hover:opacity-100 text-primary-tertiary hover:text-warning transition-all ml-2 flex-shrink-0"
                >
                  <TrashIcon />
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

// ── Center Panel — Tabs + Chat ─────────────────────────────────────────────
function CenterPanel({ messages, loading, error, bottomRef }) {
  const [activeTab, setActiveTab] = useState('chat')

  const hasResults = messages.some(m => m.role === 'assistant')
  const latestMsg  = [...messages].reverse().find(m => m.role === 'assistant')
  const sources    = latestMsg?.sources || []

  const tabs = [
    { id: 'chat',       label: 'Chat' },
    { id: 'overview',   label: 'Overview' },
    { id: 'statutes',   label: 'Statutes',   count: sources.length },
    { id: 'caselaw',    label: 'Case Law',   count: 0 },
    { id: 'multistate', label: 'Multi-State', count: 0 },
  ]

  return (
    <div>
      <div className="text-xs uppercase tracking-widest text-primary-tertiary font-semibold mb-3 pl-1">Research Results</div>
      <div className="bg-card rounded-2xl shadow-card overflow-hidden">
        {/* Tab bar */}
        <div className="flex bg-card pt-2.5 px-3 gap-0 border-b border-border-faint overflow-x-auto">
          {tabs.map(tab => {
            const isLocked  = LOCKED_TABS.has(tab.id)
            const isActive  = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-20.5 text-sm font-medium rounded-t-lg transition-all inline-flex items-center gap-1.5
                  ${isActive
                    ? 'bg-card text-accent-navy font-semibold border-b-2 border-accent-navy -mb-px'
                    : isLocked
                    ? 'text-primary-tertiary hover:bg-bg/60'
                    : 'text-primary-secondary hover:bg-bg'}`}
              >
                {tab.label}
                {isLocked && <LockIcon className="w-3 h-3 opacity-60" />}
                {!isLocked && typeof tab.count === 'number' && tab.count > 0 && (
                  <span className={`text-xs px-1.5 py-0.5 rounded-full font-semibold ${isActive ? 'bg-accent-navy text-white' : 'bg-accent-blue-soft text-accent-navy'}`}>
                    {tab.count}
                  </span>
                )}
              </button>
            )
          })}
        </div>

        {/* Tab content */}
      <div className="bg-card min-h-[400px]">
        {/* Chat tab */}
        {activeTab === 'chat' && (
          <div className="flex flex-col gap-6 p-7 h-[600px] overflow-y-auto">
              {messages.length === 0 && !loading && <EmptyState />}

              {messages.map((msg, i) => (
                <div key={i}>
                  {msg.role === 'user' ? (
                    <div className="flex justify-end">
                      <div className="max-w-[80%] bg-accent-blue-soft border border-accent-blue-mid rounded-2xl rounded-tr-sm px-5 py-3.5 text-[14px] text-primary leading-relaxed">
                        {msg.content}
                      </div>
                    </div>
                  ) : (
                    <div>
                      {msg.intent && (
                        <div className="flex gap-2 mb-3 flex-wrap">
                          <span className="inline-flex items-center px-2.5 py-1 bg-accent-navy text-white rounded-full text-[11px] font-semibold uppercase tracking-wide">
                            {msg.intent.replace('_', ' ')}
                          </span>
                          {msg.filters?.state && (
                            <span className="inline-flex items-center px-2.5 py-1 bg-accent-blue-soft text-accent-navy border border-accent-blue-mid rounded-full text-[11px] font-semibold">
                              {msg.filters.state}
                            </span>
                          )}
                          {msg.filters?.factor && (
                            <span className="inline-flex items-center px-2.5 py-1 bg-accent-blue-soft text-accent-navy border border-accent-blue-mid rounded-full text-[11px] font-semibold">
                              {msg.filters.factor}
                            </span>
                          )}
                        </div>
                      )}
                      {msg.confidence && (
                        <ConfidenceBadge
                          score={msg.confidence.overall}
                          verdict={msg.confidence.verdict}
                          details={msg.confidence}
                        />
                      )}
                      <div className="md-body text-[14px] text-primary leading-relaxed">
                        <ReactMarkdown>{msg.content}</ReactMarkdown>
                      </div>
                      {msg.sources?.length > 0 && (
                        <div className="mt-5 pt-5 border-t border-border-faint">
                          <div className="text-[11px] uppercase tracking-widest text-primary-tertiary font-semibold mb-3">
                            Sources ({msg.sources.length})
                          </div>
                          <div className="flex flex-col gap-2.5">
                            {msg.sources.map((src, j) => (
                              <div key={j} className="bg-bg rounded-xl p-4">
                                <div className="flex items-baseline justify-between mb-1.5">
                                  <div className="font-serif text-[14px] font-bold text-primary">{src.statute}</div>
                                  <span className="bg-accent-navy text-white px-2.5 py-0.5 rounded-full text-[11px] font-semibold ml-3 flex-shrink-0">
                                    {src.contributing_factor}
                                  </span>
                                </div>
                                <div className="flex items-center gap-2.5">
                                  <span className="bg-bg text-primary-secondary border border-border-soft px-2.5 py-0.5 rounded-full text-[11px] font-semibold">
                                    {src.state}
                                  </span>
                                  <a href={src.source_url} target="_blank" rel="noreferrer"
                                    className="ml-auto text-xs text-accent-blue font-medium hover:underline">
                                    View source ↗
                                  </a>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}

              {loading && <LoadingState />}
              {error && (
                <div className="fixed bottom-6 right-6 bg-warning text-white px-5 py-3 rounded-lg shadow-elevated text-sm">
                  ⚠ {error}
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          )}

          {/* Overview tab */}
        {activeTab === 'overview' && (
            <div className="p-7">
              {loading ? <LoadingState /> : !hasResults ? <EmptyState /> : <OverviewTab messages={messages} />}
            </div>
          )}

          {/* Statutes tab */}
        {activeTab === 'statutes' && (
          <div className="p-7">
            {loading ? <LoadingState /> : !hasResults ? <EmptyState /> : <StatutesTab messages={messages} />}
          </div>
        )}

          {/* Locked tabs */}
  {activeTab === 'caselaw'    && <div className="p-7"><LockedFeature feature="Case Law Interpretations" /></div>}
  {activeTab === 'multistate' && <div className="p-7"><LockedFeature feature="Multi-State Equivalents" /></div>}
        </div>

        {/* Disclaimer */}
        <div className="px-7 py-3 border-t border-border-faint text-[11px] text-primary-tertiary text-center">
          All statutes cite real source URLs. Verify before use in proceedings.
        </div>
      </div>
    </div>
  )
}

// ── Right Panel — Coverage + Evidence + Gaps + Actions ─────────────────────
function RightPanel({ stats, messages }) {
  const [openSection, setOpenSection] = useState('states')
  const toggle = key => setOpenSection(curr => curr === key ? null : key)

  const latestMsg        = [...messages].reverse().find(m => m.role === 'assistant')
  const latestSources    = latestMsg?.sources || []
  const latestConfidence = latestMsg?.confidence
  const factorsInLast    = [...new Set(latestSources.map(s => s.contributing_factor).filter(Boolean))]

  // Mock evidence/gaps/actions — replace with real backend data when available
  const evidenceItems = latestSources.length > 0 ? [
    { priority: 'high',   evidence_type: 'Police/accident report',    rationale: 'Establishes facts of the collision and officer observations.' },
    { priority: 'high',   evidence_type: 'Vehicle damage photographs', rationale: 'Documents physical evidence of impact severity.' },
    { priority: 'medium', evidence_type: 'Witness statements',         rationale: 'Corroborates the sequence of events.' },
    { priority: 'medium', evidence_type: 'Medical records',            rationale: 'Links injuries to the accident.' },
    { priority: 'low',    evidence_type: 'Cell phone records',         rationale: 'May confirm distracted driving if applicable.' },
  ] : []

  const gapItems = latestSources.length > 0 ? [
    { description: 'Case law interpreting cited statutes not yet indexed', verifiable_basis: 'Search CanLII or Westlaw for judicial interpretations.' },
    { description: 'Multi-state equivalents not automatically retrieved',  verifiable_basis: 'Use the Statutes tab to compare across jurisdictions.' },
  ] : []

  const actionItems = latestSources.length > 0 ? [
    { action: 'Verify source URLs for all cited statutes',        rationale: 'Ensure statutes are current and haven\'t been amended.' },
    { action: 'Search for case law interpreting cited sections',  rationale: 'Judicial interpretation strengthens legal arguments.' },
    { action: 'Check multi-state equivalents for comparison',     rationale: 'Useful when defendant is from another jurisdiction.' },
  ] : []

  return (
    <div>
      <div className="text-xs uppercase tracking-widest text-primary-tertiary font-semibold mb-3 pl-1">For your case</div>

      {/* Answer Quality — only when eval scores exist */}
      {latestConfidence && (
        <div className="bg-card rounded-xl shadow-card mb-2.5 overflow-hidden">
          <button
            onClick={() => toggle('quality')}
            className="w-full flex items-center justify-between gap-3 px-5 py-4 hover:bg-bg/50 transition-colors text-left"
          >
            <div className="flex items-center gap-2.5">
              <span className={`w-1 h-4 rounded-sm flex-shrink-0 ${
                latestConfidence.verdict === 'pass'    ? 'bg-success' :
                latestConfidence.verdict === 'partial' ? 'bg-warning' : 'bg-red-400'}`} />
              <div className="font-serif text-[14px] font-bold text-primary">Answer Quality</div>
            </div>
            <div className="flex items-center gap-2">
              <span className={`text-[11px] px-2 py-0.5 rounded-full font-semibold ${
                latestConfidence.verdict === 'pass'    ? 'bg-success-soft text-success' :
                latestConfidence.verdict === 'partial' ? 'bg-warning-soft text-warning' :
                                                         'bg-red-50 text-red-700'}`}>
                {Math.round((latestConfidence.overall ?? 0) * 100)}%
              </span>
              <ChevronIcon open={openSection === 'quality'} />
            </div>
          </button>
          {openSection === 'quality' && (
            <div className="px-5 pb-5 pt-1 flex flex-col gap-2">
              {[
                { label: 'Correctness',  key: 'correctness',  weight: '35%' },
                { label: 'Faithfulness', key: 'faithfulness', weight: '30%' },
                { label: 'Relevance',    key: 'relevance',    weight: '20%' },
                { label: 'Completeness', key: 'completeness', weight: '15%' },
              ].map(({ label, key, weight }) => {
                const val = latestConfidence[key] ?? 0
                const pct = Math.round(val * 100)
                return (
                  <div key={key} className="flex flex-col gap-1">
                    <div className="flex justify-between text-[11px]">
                      <span className="text-primary-secondary font-medium">{label}</span>
                      <span className="text-primary-tertiary">{pct}% <span className="opacity-50">· {weight}</span></span>
                    </div>
                    <div className="h-1.5 bg-border-soft rounded-full overflow-hidden">
                      <div className={`h-full rounded-full transition-all ${pct >= 75 ? 'bg-success' : pct >= 45 ? 'bg-warning' : 'bg-red-400'}`}
                        style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                )
              })}
              {latestConfidence.reasoning && (
                <div className="mt-2 text-[11px] text-primary-tertiary italic border-t border-border-faint pt-2">
                  {latestConfidence.reasoning}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Evidence Needed */}
      {evidenceItems.length > 0 && (
        <AccordionSection
          title="Evidence Needed"
          subtitle="Standard evidence portfolio for this case type"
          count={evidenceItems.length}
          isOpen={openSection === 'evidence'}
          onToggle={() => toggle('evidence')}
        >
          <EvidenceContent items={evidenceItems} />
        </AccordionSection>
      )}

      {/* Coverage Gaps */}
      {gapItems.length > 0 && (
        <AccordionSection
          title="Coverage Gaps"
          subtitle="Where Workplace's database is thin"
          count={gapItems.length}
          tone="warning"
          isOpen={openSection === 'gaps'}
          onToggle={() => toggle('gaps')}
        >
          <GapsContent items={gapItems} />
        </AccordionSection>
      )}

      {/* Next Research Actions */}
      {actionItems.length > 0 && (
        <AccordionSection
          title="Next Research Actions"
          subtitle="Recommended steps to strengthen the case"
          count={actionItems.length}
          isOpen={openSection === 'actions'}
          onToggle={() => toggle('actions')}
        >
          <ActionsContent items={actionItems} />
        </AccordionSection>
      )}

      {/* States Indexed */}
      <div className="bg-card rounded-xl shadow-card mb-2.5 overflow-hidden">
        <button
          onClick={() => toggle('states')}
          className="w-full flex items-center justify-between gap-3 px-5 py-4 hover:bg-bg/50 transition-colors text-left"
        >
          <div className="flex items-center gap-2.5">
            <span className="w-1 h-4 rounded-sm bg-accent-navy flex-shrink-0" />
            <div className="font-serif text-[14px] font-bold text-primary">States Indexed</div>
          </div>
          <div className="flex items-center gap-2">
            <span className="bg-accent-blue-soft text-accent-navy text-[11px] px-2 py-0.5 rounded-full font-semibold">
              {stats?.states?.length ?? 0}
            </span>
            <ChevronIcon open={openSection === 'states'} />
          </div>
        </button>
        {openSection === 'states' && (
          <div className="px-5 pb-5 pt-1">
            <div className="flex flex-wrap gap-1.5">
              {(stats?.states || []).map(st => (
                <span key={st} className="px-2.5 py-1 bg-bg border border-border-soft rounded-full text-[11px] text-primary-secondary font-medium">
                  {st}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* DB Stats */}
      <div className="bg-card rounded-xl shadow-card overflow-hidden">
        <button
          onClick={() => toggle('db')}
          className="w-full flex items-center justify-between gap-3 px-5 py-4 hover:bg-bg/50 transition-colors text-left"
        >
          <div className="flex items-center gap-2.5">
            <span className="w-1 h-4 rounded-sm bg-success flex-shrink-0" />
            <div className="font-serif text-[14px] font-bold text-primary">Database Stats</div>
          </div>
          <ChevronIcon open={openSection === 'db'} />
        </button>
        {openSection === 'db' && (
          <div className="px-5 pb-5 pt-1 grid grid-cols-2 gap-3">
            <div className="bg-bg rounded-lg p-3 text-center">
              <div className="font-serif text-xl font-bold text-accent-navy">{stats?.statutes_indexed?.toLocaleString() ?? '—'}</div>
              <div className="text-[11px] text-primary-tertiary mt-1">Statutes</div>
            </div>
            <div className="bg-bg rounded-lg p-3 text-center">
              <div className="font-serif text-xl font-bold text-accent-navy">{stats?.states?.length ?? '—'}</div>
              <div className="text-[11px] text-primary-tertiary mt-1">States</div>
            </div>
            <div className="bg-bg rounded-lg p-3 text-center col-span-2">
              <div className={`text-sm font-semibold ${stats?.llm_provider === 'anthropic' ? 'text-success' : 'text-warning'}`}>
                {stats?.llm_provider === 'anthropic' ? '✓ Claude connected' : '⏳ Placeholder LLM'}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Empty right panel when no results yet */}
      {!latestMsg && (
        <div className="bg-card rounded-2xl p-6 shadow-card text-sm text-primary-tertiary text-center mt-2">
          Run a search to see evidence needed, coverage gaps, and recommended next steps.
        </div>
      )}
    </div>
  )
}

// ── Main App ───────────────────────────────────────────────────────────────
export default function App() {
  const { messages, sessionId, loading, error, send, loadSession, newChat } = useChat()
  const [input, setInput]     = useState('')
  const [sessions, setSessions] = useState([])
  const [stats, setStats]     = useState(null)
  const bottomRef             = useRef(null)

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
    const q = (typeof text === 'string' ? text : input).trim()
    if (!q || loading) return
    setInput('')
    await send(q)
  }

  const handleExample = (text) => setInput(text)

  const handleDelete = async (id, e) => {
    e.stopPropagation()
    await deleteSession(id)
    setSessions(s => s.filter(x => x.session_id !== id))
    if (sessionId === id) newChat()
  }

  return (
    <div className="min-h-screen bg-bg">
      <TopNav stats={stats} onNewChat={newChat} />
      <div className="grid grid-cols-[26%_1fr_26%] gap-4 px-8 py-6 items-start">
        <LeftPanel
          input={input}
          setInput={setInput}
          onSend={handleSend}
          loading={loading}
          onExample={handleExample}
          sessions={sessions}
          sessionId={sessionId}
          onLoadSession={loadSession}
          onDeleteSession={handleDelete}
        />
        <CenterPanel
          messages={messages}
          loading={loading}
          error={error}
          bottomRef={bottomRef}
        />
        <RightPanel
          stats={stats}
          messages={messages}
        />
      </div>
    </div>
  )
}
