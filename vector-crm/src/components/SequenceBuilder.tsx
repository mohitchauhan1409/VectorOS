import { useEffect, useState } from 'react'
import {
  Mail,
  Linkedin,
  Clock,
  Pencil,
  Copy,
  Pause,
  Play,
  Check,
  X,
  ArrowRight,
} from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button, IconButton } from '@/components/ui/Button'
import { Segmented } from '@/components/ui/Tabs'
import { Spinner } from '@/components/ui/Misc'
import * as api from '@/lib/api'
import { ApiError } from '@/lib/api'
import { useCopy } from '@/lib/actions'
import { pct } from '@/lib/format'
import type { Sequence, Step, Variant } from '@/lib/types'

// Render a body template, showing {{merge_tags}} as inline chips.
function TemplatePreview({ text }: { text: string }) {
  const parts = text.split(/(\{\{[^}]+\}\})/g)
  return (
    <div className="whitespace-pre-line rounded-md bg-sunken p-3 font-mono text-xs leading-relaxed text-gray-600">
      {parts.map((part, i) =>
        /^\{\{.*\}\}$/.test(part) ? (
          <span
            key={i}
            className="rounded-xs bg-brand-50 px-1 py-0.5 text-2xs font-medium text-brand-700"
          >
            {part}
          </span>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </div>
  )
}

function WaitNode({ days }: { days: number }) {
  return (
    <div className="flex items-center py-1 pl-4">
      <div className="ml-[15px] h-4 w-px bg-hairline" />
      <Badge tone="neutral" className="ml-3" icon={<Clock size={11} />}>
        Wait {days} {days === 1 ? 'day' : 'days'}
      </Badge>
    </div>
  )
}

const DEMO_NOTICE = 'Demo workspace is read-only'

function useVariantSave(onSaved: (v: Variant) => void) {
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  const save = async (variantId: string, patch: api.VariantPatch) => {
    setSaving(true)
    setNotice(null)
    try {
      const updated = await api.patchVariant(variantId, patch)
      onSaved(updated)
      return true
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) setNotice(DEMO_NOTICE)
      else setNotice(err instanceof Error ? err.message : 'Could not save changes.')
      return false
    } finally {
      setSaving(false)
    }
  }

  return { save, saving, notice, setNotice }
}

// --- Email step ---
function EmailStepCard({ step, onVariantSaved }: { step: Step; onVariantSaved: (v: Variant) => void }) {
  const [variantKey, setVariantKey] = useState(step.variants[0]?.id)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<{ subject: string; body: string }>({ subject: '', body: '' })
  const { save, saving, notice, setNotice } = useVariantSave(onVariantSaved)
  const { copy, copied } = useCopy()

  const variant = step.variants.find((v) => v.id === variantKey) ?? step.variants[0]
  if (!variant) return null
  const replyRate = variant.sent_count ? variant.reply_count / variant.sent_count : 0

  const beginEdit = () => {
    setDraft({ subject: variant.subject_template ?? '', body: variant.body_template })
    setNotice(null)
    setEditing(true)
  }

  const commit = async () => {
    const ok = await save(variant.id, { subject_template: draft.subject, body_template: draft.body })
    if (ok) setEditing(false)
  }

  const copyVariant = () =>
    void copy(`Subject: ${variant.subject_template ?? ''}\n\n${variant.body_template}`, variant.id)

  return (
    <div className="flex gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gray-100 text-sm font-semibold text-gray-700">
        {step.step_order}
      </div>
      <div className="min-w-0 flex-1 rounded-md border border-hairline bg-white p-4">
        <div className="flex items-center gap-2">
          <Mail size={15} className="text-gray-500" />
          <span className="text-sm font-semibold text-gray-800">Email · Step {step.step_order}</span>
          <Badge tone="info">{step.angle}</Badge>
          <div className="ml-auto flex items-center gap-0.5">
            <IconButton
              size="sm"
              aria-label={editing ? 'Cancel editing' : 'Edit copy'}
              title={editing ? 'Cancel editing' : 'Edit copy'}
              onClick={() => (editing ? setEditing(false) : beginEdit())}
            >
              <Pencil size={14} />
            </IconButton>
            <IconButton
              size="sm"
              aria-label="Copy variant text"
              title="Copy subject + body"
              onClick={copyVariant}
            >
              {copied === variant.id ? <Check size={14} className="text-success" /> : <Copy size={14} />}
            </IconButton>
            <IconButton
              size="sm"
              aria-label={variant.is_paused ? 'Resume variant' : 'Pause variant'}
              title={
                variant.is_paused
                  ? 'Resume this variant — the bandit will start sending it again'
                  : 'Pause this variant — the bandit will stop selecting it'
              }
              disabled={saving}
              onClick={() => void save(variant.id, { is_paused: !variant.is_paused })}
            >
              {variant.is_paused ? <Play size={14} /> : <Pause size={14} />}
            </IconButton>
          </div>
        </div>

        <div className="mt-3 flex items-center gap-2">
          <Segmented
            options={step.variants.map((v) => ({ key: v.id, label: v.name }))}
            value={variant.id}
            onChange={(k) => {
              setVariantKey(k)
              setEditing(false)
            }}
          />
          {variant.is_winner && <Badge tone="success">Leading</Badge>}
          {variant.is_paused && <Badge tone="neutral">Paused</Badge>}
        </div>

        {editing ? (
          <div className="mt-3 space-y-2">
            <div>
              <div className="kv-label mb-1">Subject</div>
              <input
                value={draft.subject}
                onChange={(e) => setDraft((d) => ({ ...d, subject: e.target.value }))}
                className="h-8 w-full rounded-sm border border-hairline-strong px-2.5 text-sm focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-500/35"
              />
            </div>
            <div>
              <div className="kv-label mb-1">Body</div>
              <textarea
                value={draft.body}
                onChange={(e) => setDraft((d) => ({ ...d, body: e.target.value }))}
                className="h-40 w-full resize-none rounded-sm border border-hairline-strong p-2.5 font-mono text-xs leading-relaxed focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-500/35"
              />
            </div>
            {notice && <p className="text-xs text-warning-text">{notice}</p>}
            <div className="flex justify-end gap-2">
              <Button variant="ghost" size="sm" icon={<X size={14} />} onClick={() => setEditing(false)} disabled={saving}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                icon={saving ? <Spinner size={14} /> : <Check size={14} />}
                onClick={commit}
                disabled={saving}
              >
                Save changes
              </Button>
            </div>
          </div>
        ) : (
          <div className="mt-3 space-y-2">
            <div className="text-sm text-gray-700">
              <span className="text-gray-500">Subject:</span>{' '}
              <span className="font-medium">{variant.subject_template}</span>
            </div>
            <TemplatePreview text={variant.body_template} />
            {notice && <p className="text-xs text-warning-text">{notice}</p>}
          </div>
        )}

        <div className="mt-3 flex items-center gap-4 border-t border-hairline pt-3 text-xs">
          <Metric label="Reply rate" value={pct(replyRate)} hero />
          <Metric label="Sent" value={variant.sent_count.toLocaleString()} />
          <Metric label="Replies" value={variant.reply_count.toLocaleString()} />
        </div>
      </div>
    </div>
  )
}

// --- LinkedIn step ---
function LinkedInStepCard({ step, onVariantSaved }: { step: Step; onVariantSaved: (v: Variant) => void }) {
  const [editing, setEditing] = useState(false)
  const [body, setBody] = useState('')
  const { save, saving, notice, setNotice } = useVariantSave(onVariantSaved)
  const { copy, copied } = useCopy()

  const v = step.variants[0]
  if (!v) return null
  const replyRate = v.sent_count ? v.reply_count / v.sent_count : 0
  const isInvite = step.kind === 'invite'

  const beginEdit = () => {
    setBody(v.body_template)
    setNotice(null)
    setEditing(true)
  }

  const commit = async () => {
    const ok = await save(v.id, { body_template: body })
    if (ok) setEditing(false)
  }

  return (
    <div className="flex gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gray-100 text-sm font-semibold text-gray-700">
        {step.step_order}
      </div>
      <div className="min-w-0 flex-1 rounded-md border border-hairline bg-white p-4">
        <div className="flex items-center gap-2">
          <Linkedin size={15} className="text-gray-500" />
          <span className="text-sm font-semibold text-gray-800">
            LinkedIn · {isInvite ? 'Connection invite' : step.name}
          </span>
          {step.kind && <Badge tone={isInvite ? 'brand' : 'neutral'}>{step.kind}</Badge>}
          <div className="ml-auto flex items-center gap-0.5">
            <IconButton
              size="sm"
              aria-label={editing ? 'Cancel editing' : 'Edit copy'}
              title={editing ? 'Cancel editing' : 'Edit copy'}
              onClick={() => (editing ? setEditing(false) : beginEdit())}
            >
              <Pencil size={14} />
            </IconButton>
            <IconButton
              size="sm"
              aria-label="Copy message text"
              title="Copy message"
              onClick={() => void copy(v.body_template, v.id)}
            >
              {copied === v.id ? <Check size={14} className="text-success" /> : <Copy size={14} />}
            </IconButton>
            <IconButton
              size="sm"
              aria-label={v.is_paused ? 'Resume variant' : 'Pause variant'}
              title={v.is_paused ? 'Resume this variant' : 'Pause this variant'}
              disabled={saving}
              onClick={() => void save(v.id, { is_paused: !v.is_paused })}
            >
              {v.is_paused ? <Play size={14} /> : <Pause size={14} />}
            </IconButton>
          </div>
        </div>

        {isInvite && (
          <div className="mt-3 flex items-center gap-1.5">
            {['Invite', 'Accept', 'Message'].map((s, i) => (
              <span key={s} className="flex items-center gap-1.5">
                <span
                  className={`rounded-xs px-1.5 py-0.5 text-2xs font-medium ${
                    i === 0 ? 'bg-brand-50 text-brand-700' : 'bg-gray-100 text-gray-500'
                  }`}
                >
                  {s}
                </span>
                {i < 2 && <ArrowRight size={12} className="text-gray-400" />}
              </span>
            ))}
          </div>
        )}

        {editing ? (
          <div className="mt-3 space-y-2">
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              className="h-28 w-full resize-none rounded-sm border border-hairline-strong p-2.5 font-mono text-xs leading-relaxed focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-500/35"
            />
            {notice && <p className="text-xs text-warning-text">{notice}</p>}
            <div className="flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={() => setEditing(false)} disabled={saving}>Cancel</Button>
              <Button
                variant="primary"
                size="sm"
                icon={saving ? <Spinner size={14} /> : undefined}
                onClick={commit}
                disabled={saving}
              >
                Save changes
              </Button>
            </div>
          </div>
        ) : (
          <div className="mt-3">
            <TemplatePreview text={v.body_template} />
            {notice && <p className="mt-2 text-xs text-warning-text">{notice}</p>}
          </div>
        )}

        <div className="mt-3 flex items-center gap-4 border-t border-hairline pt-3 text-xs">
          <Metric label={isInvite ? 'Accept rate' : 'Reply rate'} value={pct(replyRate)} hero />
          <Metric label="Sent" value={v.sent_count.toLocaleString()} />
          <Metric label={isInvite ? 'Accepted' : 'Replies'} value={v.reply_count.toLocaleString()} />
          {v.is_paused && <Badge tone="neutral">Paused</Badge>}
        </div>
      </div>
    </div>
  )
}

function Metric({ label, value, hero }: { label: string; value: string; hero?: boolean }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <span className="text-gray-500">{label}</span>
      <span className={hero ? 'text-sm font-semibold text-gray-900 tnum' : 'font-medium text-gray-800 tnum'}>
        {value}
      </span>
    </div>
  )
}

export function SequenceBuilder({ sequence }: { sequence: Sequence }) {
  const [steps, setSteps] = useState<Step[]>(sequence.steps)

  useEffect(() => {
    setSteps(sequence.steps)
  }, [sequence])

  const applyVariant = (updated: Variant) =>
    setSteps((prev) =>
      prev.map((s) => ({
        ...s,
        variants: s.variants.map((v) => (v.id === updated.id ? updated : v)),
      })),
    )

  const isEmail = sequence.channel === 'email'

  if (steps.length === 0) {
    return <p className="py-6 text-sm text-gray-400">This sequence has no steps yet.</p>
  }

  return (
    <div>
      {steps.map((step, i) => (
        <div key={step.id}>
          {isEmail ? (
            <EmailStepCard step={step} onVariantSaved={applyVariant} />
          ) : (
            <LinkedInStepCard step={step} onVariantSaved={applyVariant} />
          )}
          {i < steps.length - 1 && <WaitNode days={steps[i + 1].wait_days} />}
        </div>
      ))}
      <p className="mt-4 text-center text-2xs text-gray-400">
        Sequence structure is designed by Pulse. You can edit copy and pause variants here — the
        bandit re-weights sends automatically.
      </p>
    </div>
  )
}
