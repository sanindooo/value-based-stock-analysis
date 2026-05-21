"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import Link from "next/link"
import { useFocusTrap } from "@/hooks/useFocusTrap"
import { apiFetch } from "@/lib/api"
import { scoreColor } from "@/lib/score-utils"
import MetricBadge from "./metric-badge"

export interface StockDetail {
  id: number
  stock_ticker: string
  composite_score: number
  preservation_score?: number | null
  metric_snapshot: Record<string, unknown>
  conviction_data: Record<string, number>
  summary: string | null
  stage?: string
}

interface StockAnalysis {
  id: number
  stock_ticker: string
  tier: string
  mode: string
  analysis_data: Record<string, unknown>
  created_at: string
}

interface DeepAnalysis {
  id: number
  stock_ticker: string
  report_content: Record<string, unknown>
  sources: Record<string, unknown>
  mode: string
  created_at: string
}

interface AnalysisResponse {
  ticker: string
  standard: StockAnalysis[]
  deep: DeepAnalysis[]
}

interface StockDetailModalProps {
  stock: StockDetail
  onClose: () => void
  triggerRef?: React.RefObject<HTMLElement | null>
  onStageChange?: () => void
}


function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

export default function StockDetailModal({ stock, onClose, triggerRef, onStageChange }: StockDetailModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null)
  useFocusTrap(dialogRef, true)

  const [analyses, setAnalyses] = useState<AnalysisResponse | null>(null)
  const [selectedAnalysis, setSelectedAnalysis] = useState<StockAnalysis | null>(null)
  const [analysisLoading, setAnalysisLoading] = useState(false)
  const [triggerLoading, setTriggerLoading] = useState(false)
  const [triggerError, setTriggerError] = useState<string | null>(null)
  const [taskId, setTaskId] = useState<number | null>(null)
  const [taskProgress, setTaskProgress] = useState<string | null>(null)
  const [analysisMode, setAnalysisMode] = useState<"value" | "preservation">("value")
  const [showDeepConfirm, setShowDeepConfirm] = useState(false)
  const [deepLoading, setDeepLoading] = useState(false)
  const [deepTaskId, setDeepTaskId] = useState<number | null>(null)
  const [deepProgress, setDeepProgress] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const deepPollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose()
    }
    document.addEventListener("keydown", handleKeyDown)
    return () => {
      document.removeEventListener("keydown", handleKeyDown)
      triggerRef?.current?.focus()
    }
  }, [onClose, triggerRef])

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
      if (deepPollRef.current) clearInterval(deepPollRef.current)
    }
  }, [])

  const loadAnalyses = useCallback(async (opts?: { poll?: boolean }) => {
    setAnalysisLoading(true)
    try {
      const qs = opts?.poll ? "?poll=1" : ""
      const data = await apiFetch<AnalysisResponse>(`/analysis/${stock.stock_ticker}${qs}`)
      setAnalyses(data)
    } catch {
      // Non-critical
    } finally {
      setAnalysisLoading(false)
    }
  }, [stock.stock_ticker])

  useEffect(() => {
    loadAnalyses()
  }, [loadAnalyses])

  useEffect(() => {
    if (!analyses) return
    const match = analyses.standard.find(a => a.mode === analysisMode)
    setSelectedAnalysis(match || null)
  }, [analysisMode, analyses])

  async function triggerStandardAnalysis(mode: "value" | "preservation" = analysisMode) {
    setTriggerLoading(true)
    setTriggerError(null)
    try {
      const data = await apiFetch<{ id: number; status: string }>(`/analysis?ticker=${stock.stock_ticker}&tier=standard`, {
        method: "POST",
        body: JSON.stringify({ mode }),
      })
      setTaskId(data.id)
      setTaskProgress("queued")

      let attempts = 0
      const MAX_POLL_ATTEMPTS = 120
      pollRef.current = setInterval(async () => {
        attempts++
        if (attempts > MAX_POLL_ATTEMPTS) {
          if (pollRef.current) clearInterval(pollRef.current)
          pollRef.current = null
          setTaskId(null)
          setTriggerError("Analysis timed out — try again or check server logs")
          setTriggerLoading(false)
          return
        }
        try {
          const taskData = await apiFetch<{ status: string; progress: string | null; result_id: number | null }>(`/screening/tasks/${data.id}/status`)
          setTaskProgress(taskData.progress)
          if (taskData.status === "completed" || taskData.status === "failed") {
            if (pollRef.current) clearInterval(pollRef.current)
            pollRef.current = null
            setTaskId(null)
            if (taskData.status === "completed") {
              await loadAnalyses({ poll: true })
              onStageChange?.()
            } else {
              setTriggerError("Analysis failed")
            }
            setTriggerLoading(false)
          }
        } catch {
          // Ignore polling errors
        }
      }, 3000)
    } catch (err) {
      const msg = err instanceof Error && err.message.includes("409")
        ? "Analysis already running for this stock"
        : "Failed to start analysis"
      setTriggerError(msg)
      setTriggerLoading(false)
    }
  }

  async function triggerDeepAnalysis() {
    setShowDeepConfirm(false)
    setDeepLoading(true)
    setTriggerError(null)
    try {
      const data = await apiFetch<{ tasks: Array<{ ticker: string; task_id: number }> }>("/research", {
        method: "POST",
        body: JSON.stringify({ stock_tickers: [stock.stock_ticker], mode: analysisMode }),
      })
      const taskInfo = data.tasks[0]
      if (!taskInfo) throw new Error("No task created")
      setDeepTaskId(taskInfo.task_id)
      setDeepProgress("queued")

      let deepAttempts = 0
      const MAX_DEEP_POLL_ATTEMPTS = 200
      deepPollRef.current = setInterval(async () => {
        deepAttempts++
        if (deepAttempts > MAX_DEEP_POLL_ATTEMPTS) {
          if (deepPollRef.current) clearInterval(deepPollRef.current)
          deepPollRef.current = null
          setDeepTaskId(null)
          setTriggerError("Deep analysis timed out — try again or check server logs")
          setDeepLoading(false)
          return
        }
        try {
          const taskData = await apiFetch<{ status: string; progress: string | null }>(`/research/status/${taskInfo.task_id}?poll=1`)
          setDeepProgress(taskData.progress)
          if (taskData.status === "completed" || taskData.status === "failed") {
            if (deepPollRef.current) clearInterval(deepPollRef.current)
            deepPollRef.current = null
            setDeepTaskId(null)
            if (taskData.status === "completed") {
              await loadAnalyses({ poll: true })
              onStageChange?.()
            } else {
              setTriggerError("Deep analysis failed")
            }
            setDeepLoading(false)
          }
        } catch {
          // Ignore polling errors
        }
      }, 5000)
    } catch (err) {
      const msg = err instanceof Error && err.message.includes("409")
        ? "Research already running for this stock"
        : "Failed to start deep analysis"
      setTriggerError(msg)
      setDeepLoading(false)
    }
  }

  const metrics = stock.metric_snapshot || {}
  const conviction = stock.conviction_data || {}
  const companyName = metrics.company_name as string | undefined
  const sector = metrics.sector as string | undefined
  const website = metrics.website as string | undefined
  const dataWarnings = metrics.data_warnings as Record<string, number> | undefined

  const metricEntries = Object.entries(conviction)
    .filter(([key]) => key !== "composite_score")
    .sort(([, a], [, b]) => b - a)
    .slice(0, 8)

  const analysisData = selectedAnalysis?.analysis_data || {}
  const marginHistory = Array.isArray(analysisData.margin_history) ? analysisData.margin_history as Array<{ year: string; gross_margin: number | null }> : undefined
  const newsHeadlines = Array.isArray(analysisData.news_headlines) ? analysisData.news_headlines as Array<{ headline: string; source: string; url: string; published_at: string; summary: string }> : undefined

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
      role="presentation"
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl bg-white p-6 shadow-xl"
      >
        {/* Header */}
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h2 id="modal-title" className="text-xl font-bold text-gray-900">
              {stock.stock_ticker}
            </h2>
            {companyName && (
              <p className="text-sm text-gray-500">{companyName}</p>
            )}
            <div className="mt-1 flex flex-wrap items-center gap-2">
              {sector && (
                <span className="inline-flex rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700">
                  {sector}
                </span>
              )}
              {website && (
                <a
                  href={website}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-blue-600 hover:underline"
                >
                  Website ↗
                </a>
              )}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div
              className={`flex h-12 w-12 items-center justify-center rounded-lg border text-base font-bold tabular-nums ${scoreColor(stock.composite_score)}`}
            >
              {stock.composite_score.toFixed(0)}
            </div>
            <button
              onClick={onClose}
              className="rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
              aria-label="Close"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* FMP Warning */}
        {dataWarnings && Object.keys(dataWarnings).length > 0 && (
          <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            Limited data: {Object.keys(dataWarnings).map(k => k.replace(/_/g, " ")).join(", ")} unavailable (free tier)
          </div>
        )}

        {/* Metrics */}
        {metricEntries.length > 0 && (
          <div className="mb-4 space-y-2">
            {metricEntries.map(([key, pct]) => (
              <MetricBadge
                key={key}
                name={key}
                value={metrics[key] as number | null ?? null}
                convictionPct={pct}
              />
            ))}
          </div>
        )}

        {/* Summary */}
        {stock.summary && (
          <p className="mb-4 text-sm leading-relaxed text-gray-600">
            {stock.summary}
          </p>
        )}

        {/* Analysis Section */}
        <div className="border-t border-gray-100 pt-4">
          <div className="mb-3 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-900">Standard Analysis</h3>
              <div className="flex items-center rounded-lg border border-gray-200 p-0.5">
                <button
                  onClick={() => setAnalysisMode("value")}
                  className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                    analysisMode === "value"
                      ? "bg-blue-100 text-blue-800"
                      : "text-gray-500 hover:text-gray-700"
                  }`}
                >
                  Value
                </button>
                <button
                  onClick={() => setAnalysisMode("preservation")}
                  className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                    analysisMode === "preservation"
                      ? "bg-emerald-100 text-emerald-800"
                      : "text-gray-500 hover:text-gray-700"
                  }`}
                >
                  Preservation
                </button>
              </div>
            </div>
            {analysisLoading ? (
              <p className="text-xs text-gray-400">Loading...</p>
            ) : (() => {
              const existingStandard = analyses?.standard?.find(a => a.mode === analysisMode)
              const existingDeep = analyses?.deep?.find(d => d.mode === analysisMode)
              const anyDeepRunning = deepLoading || deepTaskId !== null || stock.stage === "researching"

              return !existingStandard ? (
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    onClick={() => triggerStandardAnalysis(analysisMode)}
                    disabled={triggerLoading || taskId !== null}
                    className="rounded-lg border border-blue-200 px-3 py-1.5 text-xs font-medium text-blue-600 transition-colors hover:bg-blue-50 disabled:opacity-50"
                  >
                    {triggerLoading ? (taskProgress || "Running...") : "Run Standard"}
                  </button>
                  {existingDeep ? (
                    <Link
                      href={`/research/${stock.stock_ticker}?mode=${analysisMode}`}
                      className="rounded-lg border border-green-200 px-3 py-1.5 text-xs font-medium text-green-700 transition-colors hover:bg-green-50"
                    >
                      View Deep Report
                    </Link>
                  ) : (
                    <button
                      onClick={() => setShowDeepConfirm(true)}
                      disabled={anyDeepRunning || triggerLoading}
                      className="rounded-lg border border-purple-200 px-3 py-1.5 text-xs font-medium text-purple-600 transition-colors hover:bg-purple-50 disabled:opacity-50"
                    >
                      {anyDeepRunning ? "Research in Progress" : "Run Deep Analysis"}
                    </button>
                  )}
                </div>
              ) : (
                <div className="space-y-3">
                  <p className="text-xs text-gray-500">
                    Trend data from {formatDate(existingStandard.created_at).split(",")[0]}.
                    {existingDeep
                      ? " For the full AI-powered research report:"
                      : " Want a deeper AI-powered report?"}
                  </p>
                  <div className="flex flex-wrap items-center gap-2">
                    {existingDeep ? (
                      <Link
                        href={`/research/${stock.stock_ticker}?mode=${analysisMode}`}
                        className="rounded-lg border border-green-200 px-3 py-1.5 text-xs font-medium text-green-700 transition-colors hover:bg-green-50"
                      >
                        View Deep Report
                      </Link>
                    ) : (
                      <button
                        onClick={() => setShowDeepConfirm(true)}
                        disabled={anyDeepRunning || triggerLoading}
                        className="rounded-lg border border-purple-200 px-3 py-1.5 text-xs font-medium text-purple-600 transition-colors hover:bg-purple-50 disabled:opacity-50"
                      >
                        {anyDeepRunning ? "Research in Progress" : "Run Deep Analysis"}
                      </button>
                    )}
                  </div>
                </div>
              )
            })()}
          </div>

          {triggerError && (
            <p className="mb-3 text-xs text-red-600">{triggerError}</p>
          )}

          {/* Analysis history dropdown — only when multiple runs exist for this mode */}
          {(() => {
            const modeAnalyses = analyses?.standard.filter(a => a.mode === analysisMode) ?? []
            if (modeAnalyses.length < 2) return null
            return (
              <div className="mb-3">
                <select
                  value={selectedAnalysis?.id || ""}
                  onChange={(e) => {
                    const id = parseInt(e.target.value)
                    const found = modeAnalyses.find((a) => a.id === id)
                    if (found) setSelectedAnalysis(found)
                  }}
                  className="w-full rounded-lg border border-gray-200 px-3 py-1.5 text-sm text-gray-700"
                >
                  {modeAnalyses.map((a) => (
                    <option key={a.id} value={a.id}>
                      {formatDate(a.created_at)} — {a.tier}
                    </option>
                  ))}
                </select>
              </div>
            )
          })()}

          {/* Analysis results */}
          {selectedAnalysis && (
            <div className="space-y-3">

              {/* Preservation interpretation (preservation mode only) */}
              {selectedAnalysis.mode === "preservation" && Boolean(analysisData.pricing_power_signal) && (
                <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-xs">
                  <h4 className="mb-1 font-medium text-emerald-800">Preservation Signals</h4>
                  <div className="grid grid-cols-2 gap-2">
                    {Boolean(analysisData.margin_trend) && (
                      <div>
                        <span className="text-emerald-600">Margin Trend: </span>
                        <span className="font-medium text-emerald-800">{String(analysisData.margin_trend)}</span>
                      </div>
                    )}
                    {Boolean(analysisData.pricing_power_signal) && (
                      <div>
                        <span className="text-emerald-600">Pricing Power: </span>
                        <span className="font-medium text-emerald-800">{String(analysisData.pricing_power_signal)}</span>
                      </div>
                    )}
                    {Boolean(analysisData.dividend_reliability) && (
                      <div>
                        <span className="text-emerald-600">Dividend Reliability: </span>
                        <span className="font-medium text-emerald-800">{String(analysisData.dividend_reliability)}</span>
                      </div>
                    )}
                    {Boolean(analysisData.business_resilience) && (
                      <div>
                        <span className="text-emerald-600">Business Resilience: </span>
                        <span className="font-medium text-emerald-800">{String(analysisData.business_resilience)}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Margin History */}
              {marginHistory && marginHistory.length > 0 && (
                <div>
                  <h4 className="mb-1 text-xs font-medium text-gray-500">Margin History</h4>
                  <div className="flex gap-3 overflow-x-auto">
                    {marginHistory.map((entry) => (
                      <div key={entry.year} className="shrink-0 text-left">
                        <span className="block text-xs text-gray-400">{entry.year}</span>
                        <span className="text-sm font-medium tabular-nums text-gray-700">
                          {entry.gross_margin != null ? `${entry.gross_margin}%` : "--"}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Dividend Growth Streak */}
              {typeof analysisData.dividend_growth_streak === "number" && (
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-500">Dividend Growth Streak</span>
                  <span className="text-sm font-medium text-gray-700">
                    {analysisData.dividend_growth_streak} years
                  </span>
                </div>
              )}

              {/* Revenue Consistency */}
              {typeof analysisData.revenue_consistency === "number" && (
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-500">Revenue Volatility (std dev)</span>
                  <span className="text-sm font-medium text-gray-700">
                    {analysisData.revenue_consistency.toFixed(1)}%
                  </span>
                </div>
              )}

              {/* News Headlines */}
              {newsHeadlines && newsHeadlines.length > 0 && (
                <div>
                  <h4 className="mb-1 text-xs font-medium text-gray-500">
                    Recent News ({newsHeadlines.length})
                  </h4>
                  <div className="space-y-1.5">
                    {newsHeadlines.slice(0, 8).map((article, idx) => (
                      <a
                        key={idx}
                        href={article.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block rounded-md py-1.5 text-xs transition-colors hover:bg-gray-50"
                      >
                        <span className="font-medium text-gray-800">{article.headline}</span>
                        <span className="ml-1 text-gray-400">
                          {article.source} · {new Date(article.published_at).toLocaleDateString()}
                        </span>
                      </a>
                    ))}
                  </div>
                </div>
              )}

              {/* No data state */}
              {!marginHistory?.length && !newsHeadlines?.length && (
                <p className="text-xs text-gray-400">No trend data available for this analysis.</p>
              )}
            </div>
          )}

          {!selectedAnalysis && !analysisLoading && !(analyses?.standard?.find(a => a.mode === analysisMode)) && (
            <p className="text-xs text-gray-400">
              No analysis yet. Click &ldquo;Run Standard&rdquo; to fetch trend data.
            </p>
          )}

        </div>

        {/* Deep Analysis Confirmation Dialog */}
        {showDeepConfirm && (
          <div className="mt-4 rounded-lg border border-purple-200 bg-purple-50 p-4">
            <h4 className="text-sm font-semibold text-purple-900">Run Deep Analysis?</h4>
            <p className="mt-1 text-xs text-purple-700">
              This will fetch and read full news articles, research competitive position, and generate an AI-powered research report. This consumes API credits (Claude AI + article fetching).
            </p>
            <div className="mt-3 flex gap-2">
              <button
                onClick={triggerDeepAnalysis}
                className="rounded-lg bg-purple-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-purple-700"
              >
                Run Deep Analysis
              </button>
              <button
                onClick={() => setShowDeepConfirm(false)}
                className="rounded-lg border border-purple-200 px-3 py-1.5 text-xs font-medium text-purple-600 transition-colors hover:bg-purple-100"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
