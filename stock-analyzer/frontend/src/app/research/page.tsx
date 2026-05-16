"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { apiFetch } from "@/lib/api"
import OpinionBadge from "@/components/opinion-badge"
import ProgressPanel from "@/components/ProgressPanel"
import ViewToggle, { useViewPreference } from "@/components/ViewToggle"

interface ReportSummary {
  id: number
  stock_ticker: string
  created_at: string
  verdict: string | null
  confidence: string | null
}

interface ActiveTask {
  id: number
  status: string
  progress: string | null
  description: string | null
}

export default function ResearchPage() {
  const [reports, setReports] = useState<ReportSummary[]>([])
  const [activeTasks, setActiveTasks] = useState<ActiveTask[]>([])
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState<string | null>(null)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Filters
  const [tickerSearch, setTickerSearch] = useState("")
  const [recommendation, setRecommendation] = useState("")
  const [confidence, setConfidence] = useState("")
  const [deduplicated, setDeduplicated] = useState(true)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const { view } = useViewPreference("research-view")

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
      setToast("Failed to load research reports")
    } finally {
      setLoading(false)
    }
  }, [buildQuery])

  const loadActive = useCallback(async () => {
    try {
      const data = await apiFetch<ActiveTask[]>("/research/active")
      setActiveTasks(data)
      if (data.length === 0 && pollingRef.current) {
        clearInterval(pollingRef.current)
        pollingRef.current = null
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

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3000)
      return () => clearTimeout(timer)
    }
  }, [toast])

  function formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    })
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-sm text-gray-500">
          Loading research reports...
        </div>
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
        <ViewToggle storageKey="research-view" />
      </div>

      {toast && (
        <div
          className={`mb-4 rounded-lg px-4 py-2 text-sm font-medium ${
            toast.includes("Failed")
              ? "bg-red-50 text-red-600"
              : "bg-green-50 text-green-600"
          }`}
        >
          {toast}
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
                  createdAt={null}
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
          <a
            href="/screening"
            className="mt-3 inline-block text-sm font-medium text-blue-600 hover:text-blue-700"
          >
            Go to Screening
          </a>
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
                <a
                  key={report.id}
                  href={`/research/${report.stock_ticker}`}
                  className="flex flex-col justify-between rounded-xl border border-gray-200 bg-white p-5 transition-colors hover:border-gray-300 hover:bg-gray-50"
                >
                  <div>
                    <p className="text-sm font-semibold text-gray-900">
                      {report.stock_ticker}
                    </p>
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
                </a>
              ))}
            </div>
          ) : (
            <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
              {reports.map((report, i) => (
                <a
                  key={report.id}
                  href={`/research/${report.stock_ticker}`}
                  className={`flex items-center justify-between px-5 py-3 transition-colors hover:bg-gray-50 ${
                    i < reports.length - 1 ? "border-b border-gray-100" : ""
                  }`}
                >
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      {report.stock_ticker}
                    </p>
                    <p className="text-xs text-gray-500">
                      {formatDate(report.created_at)}
                    </p>
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
                </a>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
