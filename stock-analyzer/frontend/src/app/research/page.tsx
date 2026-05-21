"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import Link from "next/link"
import { toast } from "sonner"
import { apiFetch } from "@/lib/api"
import OpinionBadge from "@/components/opinion-badge"
import ProgressPanel from "@/components/ProgressPanel"
import ViewToggle from "@/components/ViewToggle"
import { SkeletonCard } from "@/components/Skeleton"

interface ReportSummary {
  id: number
  stock_ticker: string
  mode: string
  created_at: string
  verdict: string | null
  confidence: string | null
}

interface ActiveTask {
  id: number
  status: string
  progress: string | null
  description: string | null
  created_at: string | null
}

interface TaskStatusResponse {
  id: number
  status: string
  progress: string | null
  description: string | null
  created_at: string | null
}

export default function ResearchPage() {
  const [reports, setReports] = useState<ReportSummary[]>([])
  const [activeTasks, setActiveTasks] = useState<ActiveTask[]>([])
  const [loading, setLoading] = useState(true)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const trackedTaskIds = useRef<Set<number>>(new Set())

  // Research ticker overlay
  const [showResearchOverlay, setShowResearchOverlay] = useState(false)
  const [researchTicker, setResearchTicker] = useState("")
  const [submittingResearch, setSubmittingResearch] = useState(false)

  // Filters
  const [tickerSearch, setTickerSearch] = useState("")
  const [recommendation, setRecommendation] = useState("")
  const [confidence, setConfidence] = useState("")
  const [deduplicated, setDeduplicated] = useState(true)
  const [view, setView] = useState<"grid" | "list">(() => {
    if (typeof window === "undefined") return "grid"
    const stored = localStorage.getItem("research-view")
    return stored === "list" ? "list" : "grid"
  })
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const buildQuery = useCallback(() => {
    const params = new URLSearchParams()
    if (tickerSearch.trim()) params.set("ticker_search", tickerSearch.trim())
    if (recommendation) params.set("recommendation", recommendation)
    if (confidence) params.set("confidence", confidence)
    params.set("deduplicated", String(deduplicated))
    const qs = params.toString()
    return qs ? `?${qs}` : ""
  }, [tickerSearch, recommendation, confidence, deduplicated])

  const loadReports = useCallback(async () => {
    try {
      const data = await apiFetch<ReportSummary[]>(`/research${buildQuery()}`)
      setReports(data)
    } catch {
      toast.error("Failed to load research reports")
    } finally {
      setLoading(false)
    }
  }, [buildQuery])

  const loadActive = useCallback(async () => {
    try {
      const serverActive = await apiFetch<ActiveTask[]>("/research/active")

      // Poll each tracked task individually (catches tasks that completed too fast for /active)
      const tracked = trackedTaskIds.current
      const trackedResults: ActiveTask[] = []
      const completedIds: number[] = []

      for (const taskId of Array.from(tracked)) {
        // Skip if the server already reports this task as active
        if (serverActive.some((t) => t.id === taskId)) continue
        try {
          const status = await apiFetch<TaskStatusResponse>(`/research/${taskId}?type=status`)
          if (status.status === "completed" || status.status === "failed" || status.status === "cancelled") {
            completedIds.push(taskId)
          } else {
            trackedResults.push(status)
          }
        } catch {
          // Task may not exist yet or endpoint error — keep tracking
        }
      }

      // Remove completed tasks from tracking
      for (const id of completedIds) {
        tracked.delete(id)
      }

      // Merge: server active + still-in-progress tracked tasks
      const merged = [...serverActive, ...trackedResults]
      setActiveTasks(merged)

      if (merged.length === 0 && pollingRef.current) {
        clearInterval(pollingRef.current)
        pollingRef.current = null
      }
      if (completedIds.length > 0) {
        loadReports()
      }
    } catch {
      // Non-critical — polling will retry
    }
  }, [loadReports])

  useEffect(() => {
    loadReports()
    loadActive()
  }, [loadReports, loadActive])

  // Debounced search
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      loadReports()
    }, 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [tickerSearch, loadReports])

  // Poll active tasks every 3s
  useEffect(() => {
    if (activeTasks.length > 0 && !pollingRef.current) {
      pollingRef.current = setInterval(() => {
        loadActive()
        loadReports()
      }, 3000)
    }
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current)
        pollingRef.current = null
      }
    }
  }, [activeTasks.length, loadActive, loadReports])


  async function submitResearch() {
    const ticker = researchTicker.trim().toUpperCase()
    if (!ticker) return
    setSubmittingResearch(true)
    try {
      const response = await apiFetch<{ tasks: { ticker: string; task_id: number }[] }>("/research", {
        method: "POST",
        body: JSON.stringify({ stock_tickers: [ticker] }),
      })
      const taskId = response.tasks[0].task_id
      trackedTaskIds.current.add(taskId)
      setActiveTasks((prev) => [
        ...prev,
        { id: taskId, status: "pending", progress: "queued", description: ticker, created_at: new Date().toISOString() },
      ])
      toast.success(`Research started for ${ticker}`)
      setShowResearchOverlay(false)
      setResearchTicker("")
      if (!pollingRef.current) {
        pollingRef.current = setInterval(() => {
          loadActive()
          loadReports()
        }, 3000)
      }
    } catch {
      toast.error("Failed to start research")
    } finally {
      setSubmittingResearch(false)
    }
  }

  function formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    })
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl grid grid-cols-1 gap-4 pt-12 sm:grid-cols-2">
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
      </div>
    )
  }

  const hasFilters = !!tickerSearch || !!recommendation || !!confidence

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Research Reports</h1>
          <p className="mt-1 text-sm text-gray-500">
            Deep-dive research reports with investment opinions and source links.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowResearchOverlay(true)}
            className="rounded-lg border border-gray-200 p-2 text-gray-500 transition-colors hover:border-gray-300 hover:bg-gray-50 hover:text-gray-700"
            title="Research a specific ticker"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </button>
          <ViewToggle storageKey="research-view" onChange={setView} />
        </div>
      </div>

      {/* Research ticker overlay */}
      {showResearchOverlay && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-32">
          <div
            className="fixed inset-0 bg-black/30"
            onClick={() => setShowResearchOverlay(false)}
          />
          <div className="relative w-full max-w-md rounded-xl border border-gray-200 bg-white p-6 shadow-xl">
            <h3 className="mb-1 text-base font-semibold text-gray-900">
              Research a Stock
            </h3>
            <p className="mb-4 text-sm text-gray-500">
              Enter a ticker symbol to start a deep-dive analysis.
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                submitResearch()
              }}
              className="flex gap-2"
            >
              <input
                type="text"
                value={researchTicker}
                onChange={(e) => setResearchTicker(e.target.value.toUpperCase())}
                placeholder="e.g. AAPL"
                autoFocus
                className="flex-1 rounded-lg border border-gray-200 px-4 py-2.5 text-sm font-medium uppercase placeholder-gray-400 focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
              <button
                type="submit"
                disabled={!researchTicker.trim() || submittingResearch}
                className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
              >
                {submittingResearch ? "Starting..." : "Research"}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Active research tasks with ProgressPanel */}
      {activeTasks.length > 0 && (
        <div className="mb-6">
          <h2 className="mb-3 text-sm font-semibold text-gray-900">
            In Progress
          </h2>
          <div className="space-y-3">
            {activeTasks.map((task) => (
              <div
                key={task.id}
                className="rounded-xl border border-blue-100 bg-blue-50 px-5 py-4"
              >
                <p className="mb-2 text-sm font-medium text-gray-900">
                  Researching {task.description || "Unknown ticker"}
                </p>
                <ProgressPanel
                  status={task.status}
                  progress={task.progress}
                  progressData={null}
                  createdAt={task.created_at}
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filter bar */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <input
          type="text"
          placeholder="Search ticker..."
          value={tickerSearch}
          onChange={(e) => setTickerSearch(e.target.value)}
          className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-900 placeholder-gray-400 focus:border-gray-400 focus:outline-none"
        />
        <select
          value={recommendation}
          onChange={(e) => setRecommendation(e.target.value)}
          className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-700 focus:border-gray-400 focus:outline-none"
        >
          <option value="">All verdicts</option>
          <option value="buy">Buy</option>
          <option value="hold">Hold</option>
          <option value="avoid">Avoid</option>
        </select>
        <select
          value={confidence}
          onChange={(e) => setConfidence(e.target.value)}
          className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-700 focus:border-gray-400 focus:outline-none"
        >
          <option value="">All confidence</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
        <label className="flex items-center gap-2 text-sm text-gray-600">
          <input
            type="checkbox"
            checked={!deduplicated}
            onChange={(e) => setDeduplicated(!e.target.checked)}
            className="rounded border-gray-300"
          />
          Show all versions
        </label>
      </div>

      {reports.length === 0 && activeTasks.length === 0 && !hasFilters ? (
        <div className="rounded-xl border border-gray-200 bg-white py-16 text-center">
          <p className="text-sm text-gray-500">
            No research reports yet. Promote stocks from a screening run to
            start research.
          </p>
          <Link
            href="/screening"
            className="mt-3 inline-block text-sm font-medium text-blue-600 hover:text-blue-700"
          >
            Go to Screening
          </Link>
        </div>
      ) : reports.length === 0 && hasFilters ? (
        <div className="rounded-xl border border-gray-200 bg-white py-12 text-center">
          <p className="text-sm text-gray-500">
            No reports match your filters.
          </p>
        </div>
      ) : (
        <div>
          {activeTasks.length > 0 && (
            <h2 className="mb-3 text-sm font-semibold text-gray-900">
              Completed
            </h2>
          )}
          {view === "grid" ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {reports.map((report) => (
                <Link
                  key={report.id}
                  href={`/research/${report.stock_ticker}?mode=${report.mode}`}
                  className="flex flex-col justify-between rounded-xl border border-gray-200 bg-white p-5 transition-colors hover:border-gray-300 hover:bg-gray-50"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-semibold text-gray-900">
                        {report.stock_ticker}
                      </p>
                      <span className={`inline-flex rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                        report.mode === "preservation"
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-blue-100 text-blue-700"
                      }`}>
                        {report.mode === "preservation" ? "Pres." : "Value"}
                      </span>
                    </div>
                    <p className="mt-0.5 text-xs text-gray-500">
                      {formatDate(report.created_at)}
                    </p>
                  </div>
                  <div className="mt-3">
                    {report.verdict && report.confidence ? (
                      <OpinionBadge
                        verdict={report.verdict}
                        confidence={report.confidence}
                      />
                    ) : (
                      <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600">
                        Processing
                      </span>
                    )}
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
              {reports.map((report, i) => (
                <Link
                  key={report.id}
                  href={`/research/${report.stock_ticker}?mode=${report.mode}`}
                  className={`flex items-center justify-between px-5 py-3 transition-colors hover:bg-gray-50 ${
                    i < reports.length - 1 ? "border-b border-gray-100" : ""
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        {report.stock_ticker}
                      </p>
                      <p className="text-xs text-gray-500">
                        {formatDate(report.created_at)}
                      </p>
                    </div>
                    <span className={`inline-flex rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                      report.mode === "preservation"
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-blue-100 text-blue-700"
                    }`}>
                      {report.mode === "preservation" ? "Pres." : "Value"}
                    </span>
                  </div>
                  <div className="flex items-center gap-4">
                    {report.verdict && report.confidence ? (
                      <OpinionBadge
                        verdict={report.verdict}
                        confidence={report.confidence}
                      />
                    ) : (
                      <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600">
                        Processing
                      </span>
                    )}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
