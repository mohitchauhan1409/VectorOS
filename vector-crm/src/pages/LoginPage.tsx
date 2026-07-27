import { useState } from 'react'
import { AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Spinner } from '@/components/ui/Misc'
import { useAuth } from '@/lib/auth'

const DEMO_EMAIL = 'demo@vector.ai'
const DEMO_PASSWORD = 'demo1234'

function VectorMark({ size = 20 }: { size?: number }) {
  return (
    <span
      className="flex items-center justify-center rounded-md bg-brand-600"
      style={{ width: size * 1.6, height: size * 1.6 }}
    >
      <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
        <path
          d="M2 3.5L8 12.5L14 3.5"
          stroke="white"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  )
}

export function LoginPage() {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await login(email.trim(), password)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  const useDemo = async () => {
    setError(null)
    setBusy(true)
    try {
      await login(DEMO_EMAIL, DEMO_PASSWORD)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not sign in to the demo.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen bg-canvas">
      {/* Left — brand panel */}
      <div className="hidden w-1/2 flex-col justify-between border-r border-hairline bg-white px-14 py-12 lg:flex">
        <div className="flex items-center gap-2.5">
          <VectorMark />
          <div>
            <div className="text-base font-bold leading-tight text-gray-900">Vector</div>
            <div className="text-2xs text-gray-500">Konfyd</div>
          </div>
        </div>
        <div className="max-w-md">
          <h1 className="text-3xl font-bold tracking-[-0.02em] text-gray-900">
            The autonomous GTM engine
          </h1>
          <p className="mt-3 text-sm leading-relaxed text-gray-500">
            Vector finds processors and acquirers the moment their capital or risk exposure
            moves, sources the risk and finance leaders who own the decision, and runs
            multi-channel outreach — end to end.
          </p>
          <div className="mt-8 space-y-3">
            {[
              ['Scout', 'Reads the payments press for funding, payfac launches, portfolio M&A and new risk leaders — then scores each account against the ICP.'],
              ['Pulse', 'Runs email + LinkedIn sequences to CROs, CFOs and heads of underwriting, with self-optimizing variants.'],
              ['Closer', 'Tracks every deal past the first meeting: meeting recaps, key risks, and the next step to close.'],
            ].map(([title, desc]) => (
              <div key={title} className="flex gap-3">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-600" />
                <div>
                  <div className="text-sm font-semibold text-gray-800">{title}</div>
                  <div className="text-sm text-gray-500">{desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="text-2xs text-gray-400">© {new Date().getFullYear()} Konfyd</div>
      </div>

      {/* Right — form */}
      <div className="flex flex-1 items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-2.5 lg:hidden">
            <VectorMark />
            <span className="text-base font-bold text-gray-900">Vector</span>
          </div>

          <h2 className="text-2xl font-bold tracking-[-0.01em] text-gray-900">Sign in</h2>
          <p className="mt-1.5 text-sm text-gray-500">
            Welcome back. Enter your details to continue.
          </p>

          {error && (
            <div className="mt-5 flex items-start gap-2 rounded-md border border-[#E7B4B4] bg-danger-bg px-3 py-2.5 text-sm text-danger-text">
              <AlertCircle size={15} className="mt-0.5 shrink-0" />
              <span className="break-words">{error}</span>
            </div>
          )}

          <form onSubmit={submit} className="mt-5 space-y-3.5">
            <Field label="Email">
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                required
                autoComplete="email"
              />
            </Field>
            <Field label="Password">
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                autoComplete="current-password"
              />
            </Field>

            <Button
              type="submit"
              variant="primary"
              size="lg"
              className="!w-full"
              disabled={busy}
              icon={busy ? <Spinner size={15} /> : undefined}
            >
              Sign in
            </Button>
          </form>

          <div className="my-5 flex items-center gap-3">
            <span className="h-px flex-1 bg-hairline" />
            <span className="text-2xs uppercase tracking-[0.04em] text-gray-400">or</span>
            <span className="h-px flex-1 bg-hairline" />
          </div>

          <Button
            variant="secondary"
            size="lg"
            className="!w-full"
            disabled={busy}
            onClick={useDemo}
          >
            Use demo account
          </Button>

          <p className="mt-6 text-center text-sm text-gray-400">
            Accounts are provisioned by your Vector administrator.
          </p>
        </div>
      </div>
    </div>
  )
}

function Field({
  label,
  optional,
  children,
}: {
  label: string
  optional?: boolean
  children: React.ReactNode
}) {
  return (
    <label className="block">
      <span className="mb-1 flex items-center gap-1.5 text-2xs font-semibold uppercase tracking-[0.04em] text-gray-500">
        {label}
        {optional && <span className="font-normal normal-case tracking-normal text-gray-400">(optional)</span>}
      </span>
      {children}
    </label>
  )
}
