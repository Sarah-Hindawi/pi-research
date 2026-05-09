import { useState, useCallback } from 'react'
import { sendMessage, getSessionHistory } from '../api/client'

export function useChat() {
  const [sessionId, setSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const send = useCallback(async (query) => {
    setLoading(true)
    setError(null)

    // Optimistically add user message
    setMessages(prev => [...prev, { role: 'user', content: query, sources: [] }])

    try {
      const data = await sendMessage(query, sessionId)

      if (!sessionId) setSessionId(data.session_id)

      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: data.answer,
          sources: data.sources || [],
          intent: data.intent,
          message_id: data.message_id,
        },
      ])
    } catch (e) {
      setError(e.message)
      // Remove optimistic user message on error
      setMessages(prev => prev.slice(0, -1))
    } finally {
      setLoading(false)
    }
  }, [sessionId])

  const loadSession = useCallback(async (id) => {
    setLoading(true)
    try {
      const data = await getSessionHistory(id)
      setSessionId(id)
      setMessages(data.messages.map(m => ({
        role: m.role,
        content: m.content,
        sources: m.sources || [],
      })))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  const newChat = useCallback(() => {
    setSessionId(null)
    setMessages([])
    setError(null)
  }, [])

  return { messages, sessionId, loading, error, send, loadSession, newChat }
}
