const BASE = '/api'

export async function sendMessage(query, sessionId = null) {
  const res = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, session_id: sessionId }),
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function getSessions() {
  const res = await fetch(`${BASE}/sessions`)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function getSessionHistory(sessionId) {
  const res = await fetch(`${BASE}/sessions/${sessionId}/history`)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function deleteSession(sessionId) {
  const res = await fetch(`${BASE}/sessions/${sessionId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function getStats() {
  const res = await fetch(`${BASE}/stats`)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}
