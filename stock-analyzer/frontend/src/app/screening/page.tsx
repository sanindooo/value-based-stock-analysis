"use client"

import { useCallback, useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import { useTaskContext } from "@/contexts/TaskContext"
import ProgressPanel from "@/components/ProgressPanel"

interface ScreeningRun {
  id: number
  created_at: string
  status: string
  result_count: number
  filter_config: Record<string, unknown> | null
  task_id: number | null
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

  // Limits UI state
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [maxExamined, setMaxExamined] = useState("")
  const [maxMatches, setMaxMatches] = useState("")

  const { registerTask, activeScreeningTask } = useTaskContext()

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

  // Reload runs when a task completes
  useEffect(() => {
    if (activeScreeningTask?.status === "completed" || activeScreeningTask?.status === "cancelled") {
      loadRuns()
    }
  }, [activeScreeningTask?.status, loadRuns])

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3000)
      return () => clearTimeout(timer)
    }
  }, [toast])

  // Persist advanced collapse state
  useEffect(() => {
    const stored = localStorage.getItem("screening-advanced-open")
    if (stored === "true") setShowAdvanced(true)
  }, [])

  async function startRun() {
    setStarting(true)
    try {
      const body: Record<string, unknown> = { filter_config: null }
      const examined = parseInt(maxExamined)
      const matches = parseInt(maxMatches)
      if (examined > 0) body.max_examined = examined
      if (matches > 0) body.max_matches = matches

      const data = await apiFetch<RunResponse>("/screening", {
        method: "POST",
        body: JSON.stringify(body),
      })
      registerTask(data.task_id)
      window.location.href = `/screening/task-${data.task_id}`
    } catch (err) {
      const msg = err instanceof Error && err.message.includes("409")
        ? "A screen is already running."
        : "Failed to start screening run"
      setToast(msg)
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
      case "partial":
        return "bg-orange-50 text-orange-700"
      case "failed":
        return "bg-red-50 text-red-700"
      default:
        return "bg-gray-100 text-gray-600"
    }
  }

  const isScreenRunning = activeScreeningTask != null

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
          disabled={starting || isScreenRunning}
          className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
        >
          {starting ? "Starting..." : isScreenRunning ? "Screen Running" : "Run Screen"}
        </button>
      </div>

      {/* Advanced options */}
      <div className="mb-6">
        <button
          onClick={() => {
            const next = !showAdvanced
            setShowAdvanced(next)
            localStorage.setItem("screening-advanced-open", String(next))
          }}
          className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
        >
          <span className={`transition-transform ${showAdvanced ? "rotate-90" : ""}`}>▸</span>
          Advanced options
        </button>
        {showAdvanced && (
          <div className="mt-3 flex gap-4">
            <div>
              <label className="text-xs text-gray-500">Max stocks to examine</label>
              <input
                type="number"
                min="1"
                value={maxExamined}
                onChange={(e) => setMaxExamined(e.target.value)}
                placeholder="All"
                className="mt-1 block w-32 rounded-md border border-gray-200 px-3 py-1.5 text-sm"
              />
            </div>
            <div>
              <label className="text-xs text-gray-500">Max matches to collect</label>
              <input
                type="number"
                min="1"
                value={maxMatches}
                onChange={(e) => setMaxMatches(e.target.value)}
                placeholder="Unlimited"
                className="mt-1 block w-32 rounded-md border border-gray-200 px-3 py-1.5 text-sm"
              />
            </div>
          </div>
        )}
      </div>

      {/* Active screening progress */}
      {activeScreeningTask && (
        <div className="mb-6">
          <ProgressPanel
            status={activeScreeningTask.status}
            progress={activeScreeningTask.progress}
            progressData={activeScreeningTask.progress_data}
            createdAt={activeScreeningTask.created_at}
            errorMessage={activeScreeningTask.error_message}
          />
        </div>
      )}

      {toast && (
        <div
          className={`mb-4 rounded-lg px-4 py-2 text-sm font-medium ${
            toast.includes("Failed") || toast.includes("already")
              ? "bg-red-50 text-red-600"
              : "bg-green-50 text-green-600"
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
              href={run.status === "running" && run.task_id ? `/screening/task-${run.task_id}` : `/screening/${run.id}`}
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
