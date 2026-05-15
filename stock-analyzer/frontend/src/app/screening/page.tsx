"use client"

import { useCallback, useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"

interface ScreeningRun {
  id: number
  created_at: string
  status: string
  result_count: number
}

interface RunResponse {
  task_id: number
  run_id: number
}

export default function ScreeningPage() {
  const [runs, setRuns] = useState<ScreeningRun[]>([])
  const [loading, setLoading] = useState(true)
  const [starting, setStarting] = useState(false)
  const [toast, setToast] = useState<string | null>(null)

  const loadRuns = useCallback(async () => {
    try {
      const data = await apiFetch<ScreeningRun[]>("/screening")
      setRuns(data)
    } catch {
      setToast("Failed to load screening runs")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadRuns()
  }, [loadRuns])

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3000)
      return () => clearTimeout(timer)
    }
  }, [toast])

  async function startRun() {
    setStarting(true)
    try {
      const data = await apiFetch<RunResponse>("/screening", {
        method: "POST",
        body: JSON.stringify({ filter_config: null }),
      })
      // Navigate to results page — poll by task_id until run_id is ready
      window.location.href = `/screening/task-${data.task_id}`
    } catch {
      setToast("Failed to start screening run")
      setStarting(false)
    }
  }

  function formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    })
  }

  function statusBadge(status: string): string {
    switch (status) {
      case "completed":
        return "bg-green-50 text-green-700"
      case "running":
      case "pending":
        return "bg-yellow-50 text-yellow-700"
      case "failed":
        return "bg-red-50 text-red-700"
      default:
        return "bg-gray-100 text-gray-600"
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-sm text-gray-500">Loading screening runs...</div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Stock Screening
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Run value-based screens and triage results for deep research.
          </p>
        </div>
        <button
          onClick={startRun}
          disabled={starting}
          className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
        >
          {starting ? "Starting..." : "Run Screen"}
        </button>
      </div>

      {toast && (
        <div
          className={`mb-4 rounded-lg px-4 py-2 text-sm font-medium ${
            toast.includes("Failed") ? "bg-red-50 text-red-600" : "bg-green-50 text-green-600"
          }`}
        >
          {toast}
        </div>
      )}

      {runs.length === 0 ? (
        <div className="rounded-xl border border-gray-200 bg-white py-16 text-center">
          <p className="text-sm text-gray-500">
            No screening runs yet. Click &ldquo;Run Screen&rdquo; to get started.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {runs.map((run) => (
            <a
              key={run.id}
              href={`/screening/${run.id}`}
              className="flex items-center justify-between rounded-xl border border-gray-200 bg-white px-5 py-4 transition-colors hover:border-gray-300 hover:bg-gray-50"
            >
              <div>
                <p className="text-sm font-medium text-gray-900">
                  Run #{run.id}
                </p>
                <p className="text-xs text-gray-500">
                  {formatDate(run.created_at)}
                </p>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-sm tabular-nums text-gray-600">
                  {run.result_count} results
                </span>
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${statusBadge(run.status)}`}
                >
                  {run.status}
                </span>
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  )
}
