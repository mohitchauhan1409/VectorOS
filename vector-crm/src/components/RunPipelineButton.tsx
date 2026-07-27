import { X } from 'lucide-react'
import { Spinner } from '@/components/ui/Misc'
import { useAuth } from '@/lib/auth'
import { usePipeline } from '@/lib/pipeline'
import type { PipelineRun } from '@/lib/types'

function runSummary(run: PipelineRun): string {
  const parts: string[] = []
  if (run.companies_found) parts.push(`${run.companies_found} companies`)
  if (run.people_found) parts.push(`${run.people_found} people`)
  if (run.enrolled) parts.push(`${run.enrolled} enrolled`)
  if (run.messages_sent) parts.push(`${run.messages_sent} sent`)
  return parts.join(' · ')
}

/**
 * Passive, DISPLAY-ONLY pipeline status.
 *
 * Runs are triggered from the backend only. When the backend is running a
 * live pipeline for this workspace, this shows a progress chip; otherwise it
 * renders nothing. (Named RunPipelineButton to keep existing import sites.)
 */
export function RunPipelineButton() {
  const { user } = useAuth()
  const { isRunning, latestRun } = usePipeline()

  if (user?.is_demo) return null
  if (!isRunning || !latestRun) return null

  const summary = runSummary(latestRun)
  return (
    <span className="inline-flex h-8 items-center gap-2 rounded-sm border border-brand-200 bg-brand-50 px-3 text-sm text-brand-700">
      <Spinner size={14} />
      <span className="font-medium capitalize">{latestRun.stage ?? 'Running'}</span>
      {summary && <span className="text-brand-600/80">· {summary}</span>}
    </span>
  )
}

/** Alias kept for semantic call-sites. */
export const PipelineStatus = RunPipelineButton

/** Inline error banner for a failed pipeline run. */
export function PipelineErrorBanner() {
  const { error, clearError, latestRun } = usePipeline()
  const message = error ?? (latestRun?.status === 'failed' ? latestRun.error : null)
  if (!message) return null
  return (
    <div className="mb-4 flex items-start gap-3 rounded-md border border-[#E7B4B4] bg-danger-bg px-4 py-3">
      <div className="min-w-0 flex-1">
        <div className="text-sm font-semibold text-danger-text">Last pipeline run failed</div>
        <p className="mt-0.5 break-words text-sm text-danger-text/90">{message}</p>
      </div>
      <button
        onClick={clearError}
        className="shrink-0 text-danger-text/70 hover:text-danger-text"
        aria-label="Dismiss"
      >
        <X size={15} />
      </button>
    </div>
  )
}
