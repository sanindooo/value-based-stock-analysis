"use client"

import { useCallback, useEffect, useState } from "react"
import { toast } from "sonner"
import { apiFetch } from "@/lib/api"
import { useTaskContext } from "@/contexts/TaskContext"
import ProgressPanel from "@/components/ProgressPanel"
import { SkeletonRunCard } from "@/components/Skeleton"
import { METRIC_LABELS } from "@/components/metric-config"

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
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null)
  const [expandedConfigId, setExpandedConfigId] = useState<number | null>(null)

  // Limits UI state
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [maxExamined, setMaxExamined] = useState("")
  const [maxMatches, setMaxMatches] = useState("")

  const { registerTask, activeScreeningTask, lastCompletedTask } = useTaskContext()

  const loadRuns = useCallback(async () => {
    try {
      const data = await apiFetch<ScreeningRun[]>("/screening")
      setRuns(data)
    } catch {
      toast.error("Failed to load screening runs")
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
    } catch (err) {
      const msg = err instanceof Error && err.message.includes("409")
        ? "A screen is already running."
        : "Failed to start screening run"
      toast.error(msg)
    } finally {
      setStarting(false)
    }
  }

  async function cancelTask() {
    if (!activeScreeningTask) return
    try {
      await apiFetch(`/screening/tasks/${activeScreeningTask.id}/cancel`, {
        method: "POST",
      })
    } catch {
      toast.error("Failed to cancel task")
    }
  }

  async function deleteRun(runId: number) {
    setDeletingId(runId)
    setConfirmDeleteId(null)
    try {
      await apiFetch(`/screening/runs/${runId}`, { method: "DELETE" })
      setRuns((prev) => prev.filter((r) => r.id !== runId))
      toast.success("Run deleted")
    } catch {
      toast.error("Failed to delete run")
    } finally {
      setDeletingId(null)
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
      <div className="mx-auto max-w-3xl space-y-3 pt-12">
        <SkeletonRunCard />
        <SkeletonRunCard />
        <SkeletonRunCard />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
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
          className="w-full rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50 sm:w-auto"
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
          <div className="mt-3 flex flex-col gap-4 sm:flex-row">
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
          <div className="mt-3 flex items-center gap-3">
            {(activeScreeningTask.status === "running" || activeScreeningTask.status === "pending") && (
              <button
                onClick={cancelTask}
                className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 transition-colors hover:bg-red-50 hover:border-red-200 hover:text-red-600"
              >
                Cancel
              </button>
            )}
          </div>
        </div>
      )}
      {!activeScreeningTask && lastCompletedTask && lastCompletedTask.result_id && (
        <div className="mb-6 flex items-center gap-3 rounded-xl border border-green-200 bg-green-50 px-5 py-3">
          <span className="text-sm text-green-700">
            {lastCompletedTask.status === "completed" ? "Screening complete" : lastCompletedTask.status === "failed" ? "Screening failed" : "Screening cancelled"}
          </span>
          {lastCompletedTask.status === "completed" && (
            <a
              href={`/screening/${lastCompletedTask.result_id}`}
              className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-green-700"
            >
              View Results
            </a>
          )}
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
          {runs.map((run) => {
            const isRunning = run.status === "running" || run.status === "pending"
            const isDeleting = deletingId === run.id
            const isConfirming = confirmDeleteId === run.id

            return (
              <div
                key={run.id}
                className={`group relative rounded-xl border border-gray-200 bg-white transition-colors hover:border-gray-300 hover:bg-gray-50 ${isDeleting ? "opacity-50" : ""}`}
              >
                <a
                  href={isRunning && run.task_id ? `/screening/task-${run.task_id}` : `/screening/${run.id}`}
                  className="flex items-center justify-between px-5 py-4"
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
                    {run.filter_config && Object.keys(run.filter_config).length > 0 && (
                      <button
                        onClick={(e) => {
                          e.preventDefault()
                          e.stopPropagation()
                          setExpandedConfigId(expandedConfigId === run.id ? null : run.id)
                        }}
                        className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
                        title="View run settings"
                      >
                        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        </svg>
                        Settings
                      </button>
                    )}
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

                {/* Expanded settings */}
                {expandedConfigId === run.id && run.filter_config && (
                  <div className="border-t border-gray-100 px-5 py-3" onClick={(e) => e.stopPropagation()}>
                    <p className="mb-2 text-xs font-medium text-gray-500">Thresholds used for this run</p>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(run.filter_config).map(([key, value]) => {
                        const label = METRIC_LABELS[key] || key.replace(/_/g, " ")
                        const cfg = value as { min?: number; max?: number }
                        const parts: string[] = []
                        if (cfg.min != null) parts.push(`min ${cfg.min}`)
                        if (cfg.max != null) parts.push(`max ${cfg.max}`)
                        return (
                          <span
                            key={key}
                            className="inline-flex items-center gap-1 rounded-md bg-gray-50 px-2 py-1 text-xs text-gray-600"
                          >
                            <span className="font-medium">{label}:</span>
                            {parts.join(", ")}
                          </span>
                        )
                      })}
                    </div>
                  </div>
                )}

                {/* Delete button */}
                {!isConfirming && (
                  <button
                    onClick={(e) => {
                      e.preventDefault()
                      e.stopPropagation()
                      if (isRunning) {
                        toast.error("Cancel the run before deleting.")
                        return
                      }
                      setConfirmDeleteId(run.id)
                    }}
                    disabled={isDeleting}
                    className="absolute right-2 top-2 rounded-lg p-1.5 text-gray-300 opacity-0 transition-opacity hover:bg-red-50 hover:text-red-500 group-hover:opacity-100 sm:right-3 sm:top-3"
                    title={isRunning ? "Cancel the run before deleting" : "Delete run"}
                  >
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                )}

                {/* Confirmation overlay */}
                {isConfirming && (
                  <div className="absolute inset-0 flex items-center justify-center rounded-xl bg-white/95">
                    <div className="flex items-center gap-3">
                      <span className="text-sm text-gray-700">Delete this run?</span>
                      <button
                        onClick={() => deleteRun(run.id)}
                        className="rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700"
                      >
                        Delete
                      </button>
                      <button
                        onClick={() => setConfirmDeleteId(null)}
                        className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm font-medium text-gray-600 hover:bg-gray-50"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
