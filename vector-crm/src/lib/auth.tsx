import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import * as api from './api'
import type { User } from './types'

interface AuthContextValue {
  user: User | null
  token: string | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => api.getStoredUser())
  const [token, setTokenState] = useState<string | null>(() => api.getToken())
  const [loading, setLoading] = useState(true)

  // On mount, validate any persisted token against /api/auth/me.
  useEffect(() => {
    let cancelled = false
    if (!api.getToken()) {
      setLoading(false)
      return
    }
    api
      .me()
      .then((u) => {
        if (cancelled) return
        setUser(u)
        api.setStoredUser(u)
      })
      .catch(() => {
        if (cancelled) return
        api.setToken(null)
        api.setStoredUser(null)
        setUser(null)
        setTokenState(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const apply = useCallback((res: { token: string; user: User }) => {
    api.setToken(res.token)
    api.setStoredUser(res.user)
    setTokenState(res.token)
    setUser(res.user)
  }, [])

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await api.login(email, password)
      apply(res)
    },
    [apply],
  )

  const logout = useCallback(() => {
    api.setToken(null)
    api.setStoredUser(null)
    setUser(null)
    setTokenState(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
