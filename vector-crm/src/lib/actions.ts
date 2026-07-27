/**
 * Small client-side actions shared across the app: clipboard, CSV export, and
 * locally-persisted notes.
 *
 * These are deliberately browser-only. The Vector API is display-only by design
 * (the engine owns the data), so anything that would need a write endpoint —
 * creating contacts, enrolling people in sequences — is not faked here.
 */

import { useCallback, useRef, useState } from 'react'

// ---------- clipboard ----------

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    // Fallback for non-secure contexts where the async clipboard API is blocked.
    try {
      const el = document.createElement('textarea')
      el.value = text
      el.style.position = 'fixed'
      el.style.opacity = '0'
      document.body.appendChild(el)
      el.select()
      const ok = document.execCommand('copy')
      document.body.removeChild(el)
      return ok
    } catch {
      return false
    }
  }
}

/** Copy with a short-lived "Copied" flag, keyed so several buttons can share one hook. */
export function useCopy(resetMs = 1600) {
  const [copied, setCopied] = useState<string | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const copy = useCallback(
    async (text: string, key = 'default') => {
      const ok = await copyText(text)
      if (!ok) return false
      if (timer.current) clearTimeout(timer.current)
      setCopied(key)
      timer.current = setTimeout(() => setCopied(null), resetMs)
      return true
    },
    [resetMs],
  )

  return { copy, copied }
}

// ---------- CSV ----------

function cell(value: unknown): string {
  if (value === null || value === undefined) return ''
  const s = String(value)
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

export interface CsvColumn<T> {
  header: string
  value: (row: T) => unknown
}

export function toCsv<T>(rows: T[], columns: CsvColumn<T>[]): string {
  const head = columns.map((c) => cell(c.header)).join(',')
  const body = rows.map((r) => columns.map((c) => cell(c.value(r))).join(','))
  return [head, ...body].join('\n')
}

export function downloadCsv<T>(filename: string, rows: T[], columns: CsvColumn<T>[]): void {
  // BOM keeps Excel from mangling non-ASCII names.
  const blob = new Blob(['﻿' + toCsv(rows, columns)], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename.endsWith('.csv') ? filename : `${filename}.csv`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export function stamped(prefix: string): string {
  return `${prefix}-${new Date().toISOString().slice(0, 10)}.csv`
}

// ---------- notes (localStorage) ----------

export interface Note {
  id: string
  body: string
  created_at: string
}

const NOTES_KEY = 'vector_notes'

type NoteStore = Record<string, Note[]>

function readAll(): NoteStore {
  try {
    return JSON.parse(localStorage.getItem(NOTES_KEY) ?? '{}') as NoteStore
  } catch {
    return {}
  }
}

export function getNotes(personId: string): Note[] {
  return readAll()[personId] ?? []
}

export function addNote(personId: string, body: string): Note[] {
  const all = readAll()
  const note: Note = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    body,
    created_at: new Date().toISOString(),
  }
  all[personId] = [note, ...(all[personId] ?? [])]
  localStorage.setItem(NOTES_KEY, JSON.stringify(all))
  return all[personId]
}

export function deleteNote(personId: string, noteId: string): Note[] {
  const all = readAll()
  all[personId] = (all[personId] ?? []).filter((n) => n.id !== noteId)
  localStorage.setItem(NOTES_KEY, JSON.stringify(all))
  return all[personId]
}
