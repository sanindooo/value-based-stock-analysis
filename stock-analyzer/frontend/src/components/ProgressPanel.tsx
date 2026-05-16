"use client"

import { useEffect, useState } from "react"
import type { ProgressData } from "@/contexts/TaskContext"

interface ProgressPanelProps {
  status: string
  progress: string | null
  progressData: ProgressData | null
  createdAt: string | null
  errorMessage?: string | null
}

function formatElapsed(createdAt: string | null): string {
  if (!createdAt) return "Unknown duration"
  const start = new Date(createdAt).getTime()
  const elapsed = Math.floor((Date.now() - start) / 1000)
  if (elapsed < 60) return `${elapsed}s`
  const minutes = Math.floor(elapsed / 60)
  const seconds = elapsed % 60
  return `${minutes}m ${seconds}s`
}

function stageLabel(stage: string | null): string {
  const labels: Record<string, string> = {
    queued: "Queued",
    fetching_data: "Fetching market data",
    screening: "Screening stocks",
    scoring: "Computing scores",
    done: "Complete",
    cancelled: "Cancelled",
    cancelling: "Cancelling...",
  }
  return labels[stage ?? ""] ?? stage ?? "Processing"
}

export default function ProgressPanel({
  status,
  progress,
  progressData,
  createdAt,
  errorMessage,
}: ProgressPanelProps) {
  const [elapsed, setElapsed] = useState(formatElapsed(createdAt))

  useEffect(() => {
    if (status === "completed" || status === "failed" || status === "cancelled") return
    const interval = setInterval(() => setElapsed(formatElapsed(createdAt)), 1000)
    return () => clearInterval(interval)
  }, [createdAt, status])

  const isActive = status === "running" || status === "pending" || status === "cancelling"

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5">
      {/* Stage + elapsed */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isActive && (
            <div className="h-2 w-2 animate-pulse rounded-full bg-blue-500" />
          )}
          <span className="text-sm font-medium text-gray-900">
            {stageLabel(progressData?.stage ?? progress)}
          </span>
        </div>
        <span className="text-xs tabular-nums text-gray-500">{elapsed}</span>
      </div>

      {/* Counts */}
      {progressData && (
        <div className="mb-3 grid grid-cols-3 gap-3">
          <div className="rounded-lg bg-gray-50 px-3 py-2 text-center">
            <div className="text-lg font-bold tabular-nums text-gray-900">
              {progressData.stocks_examined}
            </div>
            <div className="text-xs text-gray-500">Examined</div>
          </div>
          <div className="rounded-lg bg-gray-50 px-3 py-2 text-center">
            <div className="text-lg font-bold tabular-nums text-green-700">
              {progressData.matches_found}
            </div>
            <div className="text-xs text-gray-500">Matches</div>
          </div>
          <div className="rounded-lg bg-gray-50 px-3 py-2 text-center">
            <div className="text-lg font-bold tabular-nums text-gray-900">
              {progressData.total_stocks}
            </div>
            <div className="text-xs text-gray-500">Total</div>
          </div>
        </div>
      )}

      {/* Activity log */}
      {progressData && progressData.log_entries.length > 0 && (
        <div className="max-h-32 overflow-y-auto rounded-lg bg-gray-50 px-3 py-2">
          {progressData.log_entries.map((entry, i) => (
            <div key={i} className="text-xs text-gray-600">
              {entry.message}
            </div>
          ))}
        </div>
      )}

      {/* Error */}
      {errorMessage && (
        <div className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">
          {errorMessage}
        </div>
      )}
    </div>
  )
}
