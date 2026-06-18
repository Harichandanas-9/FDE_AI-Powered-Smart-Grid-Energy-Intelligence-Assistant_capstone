/**
 * Custom hook for WebSocket connections — manages the socket lifecycle,
 * reconnects with exponential backoff, and maintains a rolling message buffer.
 */
import { useEffect, useRef, useState } from 'react'

/**
 * useWebSocket(path, { enabled, maxMessages, onMessage })
 *
 * - `path` is relative ('/api/v1/ws/telemetry'). The hook resolves the URL
 *   against window.location and rewrites http(s) -> ws(s).
 * - Keeps the last `maxMessages` ticks in state so consumers can chart them.
 * - Auto-reconnects with exponential backoff up to 30 s.
 */
export function useWebSocket(path, {
  enabled = true,
  maxMessages = 200,
  onMessage,
  query,                  // optional query-string object
} = {}) {
  const [messages, setMessages] = useState([])
  const [status,   setStatus]   = useState('idle')
  const [error,    setError]    = useState(null)
  const wsRef = useRef(null)
  const retryRef = useRef(0)

  useEffect(() => {
    if (!enabled) {
      setStatus('paused')
      if (wsRef.current) { wsRef.current.close(); wsRef.current = null }
      return
    }

    let cancelled = false

    const buildUrl = () => {
      const apiBase = import.meta.env.VITE_API_URL || ''
      let base
      if (apiBase) {
        base = apiBase.replace(/^http/, 'ws')
      } else {
        const loc = window.location
        base = (loc.protocol === 'https:' ? 'wss://' : 'ws://') + loc.host
      }
      const qs = query
        ? '?' + new URLSearchParams(query).toString()
        : ''
      return base + path + qs
    }

    const connect = () => {
      if (cancelled) return
      const url = buildUrl()
      setStatus('connecting')
      let ws
      try { ws = new WebSocket(url) }
      catch (e) {
        setError(e.message); setStatus('error'); scheduleRetry(); return
      }
      wsRef.current = ws

      ws.onopen = () => {
        retryRef.current = 0
        setStatus('open'); setError(null)
      }
      ws.onmessage = (ev) => {
        let payload
        try { payload = JSON.parse(ev.data) }
        catch { payload = ev.data }
        setMessages((prev) => {
          const next = [...prev, payload]
          if (next.length > maxMessages) next.splice(0, next.length - maxMessages)
          return next
        })
        if (onMessage) onMessage(payload)
      }
      ws.onerror = () => setError('socket error')
      ws.onclose = () => {
        setStatus('closed')
        if (!cancelled) scheduleRetry()
      }
    }

    /* Exponential backoff: delay doubles each attempt, capped at 30 s. */
    const scheduleRetry = () => {
      retryRef.current = Math.min(retryRef.current + 1, 6)
      const delay = Math.min(30000, 500 * 2 ** retryRef.current)
      setTimeout(() => { if (!cancelled) connect() }, delay)
    }

    connect()
    return () => {
      cancelled = true
      if (wsRef.current) { wsRef.current.close(); wsRef.current = null }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, path, JSON.stringify(query || {})])

  const clear = () => setMessages([])

  return { messages, status, error, clear }
}
