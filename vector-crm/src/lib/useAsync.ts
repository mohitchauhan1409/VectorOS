import { useCallback, useEffect, useRef, useState } from 'react'

export interface AsyncState<T> {
  data: T | null
  loading: boolean
  error: string | null
  reload: () => void
}

/**
 * Runs an async function on mount and whenever `deps` change.
 * Returns the resolved data, loading + error flags, and a manual `reload`.
 * Stale responses (from a superseded call) are discarded.
 */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)
  const callId = useRef(0)

  const reload = useCallback(() => setNonce((n) => n + 1), [])

  useEffect(() => {
    const id = ++callId.current
    let cancelled = false
    setLoading(true)
    setError(null)
    fn()
      .then((result) => {
        if (cancelled || id !== callId.current) return
        setData(result)
      })
      .catch((err) => {
        if (cancelled || id !== callId.current) return
        setError(err instanceof Error ? err.message : 'Something went wrong.')
      })
      .finally(() => {
        if (cancelled || id !== callId.current) return
        setLoading(false)
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce])

  return { data, loading, error, reload }
}

/** Debounce a fast-changing value (e.g. a search box) by `delay` ms. */
export function useDebounced<T>(value: T, delay = 250): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(t)
  }, [value, delay])
  return debounced
}
