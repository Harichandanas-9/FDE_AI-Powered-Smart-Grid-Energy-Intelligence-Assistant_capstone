import { useEffect, useRef, useState } from 'react'

/**
 * useApi(fetcher, deps?, options?) — generic async fetcher with reload + error.
 * Options: { pollMs?: number } to enable polling.
 */
export function useApi(fetcher, deps = [], { pollMs } = {}) {
  const [data,    setData]    = useState(null)
  const [error,   setError]   = useState(null)
  const [loading, setLoading] = useState(true)
  const live = useRef(true)

  const reload = async () => {
    setLoading(true)
    try {
      const r = await fetcher()
      if (live.current) { setData(r); setError(null) }
    } catch (e) {
      if (live.current) setError(e?.friendly || e?.message || 'Request failed')
    } finally {
      if (live.current) setLoading(false)
    }
  }

  useEffect(() => {
    live.current = true
    reload()
    let id
    if (pollMs) id = setInterval(reload, pollMs)
    return () => { live.current = false; if (id) clearInterval(id) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return { data, error, loading, reload }
}
