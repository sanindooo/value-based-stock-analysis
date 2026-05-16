"use client"

import { useEffect, useState } from "react"

interface ViewToggleProps {
  storageKey: string
  onChange?: (view: "grid" | "list") => void
}

export function useViewPreference(storageKey: string) {
  const [view, setView] = useState<"grid" | "list">("grid")

  useEffect(() => {
    const stored = localStorage.getItem(storageKey)
    if (stored === "list" || stored === "grid") setView(stored)
  }, [storageKey])

  const toggle = (v: "grid" | "list") => {
    setView(v)
    localStorage.setItem(storageKey, v)
  }

  return { view, toggle }
}

export default function ViewToggle({ storageKey, onChange }: ViewToggleProps) {
  const { view, toggle } = useViewPreference(storageKey)

  const handleToggle = (v: "grid" | "list") => {
    toggle(v)
    onChange?.(v)
  }

  return (
    <div className="inline-flex rounded-lg border border-gray-200 bg-white p-0.5">
      <button
        onClick={() => handleToggle("grid")}
        className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
          view === "grid"
            ? "bg-gray-900 text-white"
            : "text-gray-600 hover:text-gray-900"
        }`}
        aria-label="Grid view"
        aria-pressed={view === "grid"}
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
        </svg>
      </button>
      <button
        onClick={() => handleToggle("list")}
        className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
          view === "list"
            ? "bg-gray-900 text-white"
            : "text-gray-600 hover:text-gray-900"
        }`}
        aria-label="List view"
        aria-pressed={view === "list"}
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>
    </div>
  )
}
