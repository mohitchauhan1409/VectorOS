import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import * as api from './api'
import type { PipelineRun } from './types'

/**
 * Pipeline runs are triggered from the BACKEND only (see backend/manage.py).
 * The frontend just observes: it polls run status so the UI can show a live
 * run's progress and auto-refresh data when a run finishes.
 */
interface PipelineContextValue {
  latestRun: PipelineRun | null
  isRunning: boolean
  error: string | null
  /** Increments whenever a run finishes successfully — use as a data-refresh dep. */
  dataVersion: number
  clearError: () => void
}

const PipelineContext = createContext<PipelineContextValue | null>(null)

const IDLE_POLL_MS = 15000
const ACTIVE_POLL_MS = 4000

export function PipelineProvider({ children }: { children: ReactNode }) {
  const [latestRun, setLatestRun] = useState<PipelineRun | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [dataVersion, setDataVersion] = useState(0)
  const timer = useRef<ReturnType<typeof setInterval> | null>(null)
  const prevStatus = useRef<string | null>(null)

  const isRunning = latestRun?.status === 'running'

  const poll = useCallback(async () => {
    try {
      const { items } = await api.getRuns()
      const run = items[0] ?? null
      setLatestRun(run)
      if (run && prevStatus.current === 'running' && run.status !== 'running') {
        if (run.status === 'succeeded') setDataVersion((v) => v + 1)
        if (run.status === 'failed' && run.error) setError(run.error)
      }
      prevStatus.current = run?.status ?? null
    } catch {
      /* ignore transient poll errors */
    }
  }, [])

  useEffect(() => {
    void poll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Poll faster while a run is active, slowly otherwise (to pick up a new BE run).
  useEffect(() => {
    const interval = isRunning ? ACTIVE_POLL_MS : IDLE_POLL_MS
    if (timer.current) clearInterval(timer.current)
    timer.current = setInterval(() => void poll(), interval)
    return () => {
      if (timer.current) {
        clearInterval(timer.current)
        timer.current = null
      }
    }
  }, [isRunning, poll])

  const clearError = useCallback(() => setError(null), [])

  return (
    <PipelineContext.Provider value={{ latestRun, isRunning, error, dataVersion, clearError }}>
      {children}
    </PipelineContext.Provider>
  )
}

export function usePipeline(): PipelineContextValue {
  const ctx = useContext(PipelineContext)
  if (!ctx) throw new Error('usePipeline must be used within PipelineProvider')
  return ctx
}
