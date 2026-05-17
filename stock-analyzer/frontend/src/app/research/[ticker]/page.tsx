"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { apiFetch } from "@/lib/api"
import ResearchReport from "@/components/research-report"

interface MetricDirection {
  higher_is_better: boolean
  range_min: number
  range_max: number
}

interface ThresholdBounds {
  min: number | null
  max: number | null
}

interface ThresholdsResponse {
  thresholds: Record<string, ThresholdBounds>
  directions: Record<string, MetricDirection>
}

type TrafficColor = "green" | "orange" | "red" | "gray"

function getTrafficColor(
  key: string,
  value: number,
  directions: Record<string, MetricDirection>,
  thresholds: Record<string, ThresholdBounds>
): TrafficColor {
  const dir = directions[key]
  if (!dir) return "gray"

  const bounds = thresholds[key]
  if (!bounds) return "gray"

  const range = dir.range_max - dir.range_min
  const nearBuffer = range * 0.2

  if (dir.higher_is_better) {
    const threshold = bounds.min
    if (threshold == null) return "gray"
    if (value >= threshold) return "green"
    if (value >= threshold - nearBuffer) return "orange"
    return "red"
  } else {
    const threshold = bounds.max
    if (threshold == null) return "gray"
    if (value <= threshold) return "green"
    if (value <= threshold + nearBuffer) return "orange"
    return "red"
  }
}

const COLOR_CLASSES: Record<TrafficColor, string> = {
  green: "text-green-700",
  orange: "text-amber-600",
  red: "text-red-600",
  gray: "text-gray-900",
}

const DOT_CLASSES: Record<TrafficColor, string> = {
  green: "text-green-500",
  orange: "text-amber-500",
  red: "text-red-500",
  gray: "text-gray-300",
}

interface ReportSummary {
  id: number
  stock_ticker: string
  created_at: string
  verdict: string | null
  confidence: string | null
}

interface FullReport {
  id: number
  stock_ticker: string
  report_content: Record<string, unknown>
  sources: Record<string, unknown>
  created_at: string
}

interface ScreeningRun {
  id: number
  created_at: string
  status: string
  result_count: number
}

interface StockResult {
  id: number
  stock_ticker: string
  composite_score: number
  metric_snapshot: Record<string, number | null>
  conviction_data: Record<string, number>
  summary: string | null
  stage: string
}

interface ResultsPage {
  results: StockResult[]
  total: number
}

interface StockData {
  [key: string]: number | string | null
  last_updated: string | null
}

export default function ResearchTickerPage() {
  const params = useParams<{ ticker: string }>()
  const ticker = params.ticker.toUpperCase()

  const [report, setReport] = useState<FullReport | null>(null)
  const [metrics, setMetrics] = useState<Record<string, number | null> | null>(
    null
  )
  const [lastUpdated, setLastUpdated] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [thresholds, setThresholds] = useState<ThresholdsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Fetch report: first get the report list to find the ID for this ticker
  const fetchReport = useCallback(async () => {
    try {
      const summaries = await apiFetch<ReportSummary[]>("/research")
      const match = summaries.find(
        (s) => s.stock_ticker.toUpperCase() === ticker
      )
      if (!match) {
        setError("No research report found for this ticker.")
        return
      }
      const full = await apiFetch<FullReport>(`/research/${match.id}`)
      setReport(full)
    } catch {
      setError("Failed to load research report.")
    } finally {
      setLoading(false)
    }
  }, [ticker])

  // Fetch metrics — try screening results first, fall back to direct stock data
  const fetchMetrics = useCallback(async () => {
    try {
      // Try screening results first
      const runs = await apiFetch<ScreeningRun[]>("/screening")
      const completedRuns = runs.filter(
        (r) => r.status === "completed" && r.result_count > 0
      )
      for (const run of completedRuns) {
        const data = await apiFetch<ResultsPage>(
          `/screening/${run.id}?limit=200&offset=0&sort_by=composite_score&order=desc`
        )
        const match = data.results.find(
          (r) => r.stock_ticker.toUpperCase() === ticker
        )
        if (match) {
          setMetrics(match.metric_snapshot)
          return
        }
      }
    } catch {
      // Fall through to direct fetch
    }

    // Fallback: fetch directly from stock data (auto-fetches from Yahoo if not cached)
    try {
      const stock = await apiFetch<StockData>(`/data/stocks/${ticker}?fetch=true`)
      setLastUpdated(stock.last_updated as string | null)
      const numericFields: Record<string, number | null> = {}
      for (const [key, val] of Object.entries(stock)) {
        if (key === "last_updated" || key === "website") continue
        if (typeof val === "number" || val === null) {
          numericFields[key] = val as number | null
        }
      }
      setMetrics(numericFields)
    } catch {
      // Non-critical — sidebar just won't show
    }
  }, [ticker])

  async function refreshMetrics() {
    setRefreshing(true)
    try {
      const stock = await apiFetch<StockData>(`/data/stocks/${ticker}/refresh`, {
        method: "POST",
      })
      setLastUpdated(stock.last_updated as string | null)
      const numericFields: Record<string, number | null> = {}
      for (const [key, val] of Object.entries(stock)) {
        if (key === "last_updated" || key === "website") continue
        if (typeof val === "number" || val === null) {
          numericFields[key] = val as number | null
        }
      }
      setMetrics(numericFields)
    } catch {
      // Silently fail
    } finally {
      setRefreshing(false)
    }
  }

  useEffect(() => {
    fetchReport()
    fetchMetrics()
    apiFetch<ThresholdsResponse>("/screening/thresholds")
      .then(setThresholds)
      .catch(() => {})
  }, [fetchReport, fetchMetrics])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-sm text-gray-500">Loading report...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <p className="text-sm text-red-600">{error}</p>
        <Link
          href="/research"
          className="mt-4 text-sm text-blue-600 hover:underline"
        >
          Back to Research
        </Link>
      </div>
    )
  }

  if (!report) return null

  const PCT_METRICS = new Set([
    "roe", "roa", "roi", "gross_margin", "operating_margin",
    "net_profit_margin", "dividend_yield", "dividend_payout",
    "eps_growth_this_year", "eps_growth_next_year",
    "eps_growth_past_5y", "eps_growth_next_5y",
    "sales_growth_past_5y", "projected_earnings_growth",
  ])

  const SKIP_FIELDS = new Set([
    "sector", "company_name", "data_warnings", "website",
    "market_cap", "price",
  ])

  const METRIC_LABELS: Record<string, string> = {
    pe_ratio: "P/E",
    forward_pe: "Fwd P/E",
    pb_ratio: "P/B",
    ps_ratio: "P/S",
    peg_ratio: "PEG",
    price_to_fcf: "P/FCF",
    price_to_cash: "P/Cash",
    roe: "ROE",
    roa: "ROA",
    roi: "ROI",
    gross_margin: "Gross Margin",
    operating_margin: "Op. Margin",
    net_profit_margin: "Net Margin",
    current_ratio: "Current Ratio",
    quick_ratio: "Quick Ratio",
    debt_to_equity: "D/E",
    lt_debt_to_equity: "LT D/E",
    debt_to_ebitda: "Debt/EBITDA",
    dividend_yield: "Div. Yield",
    dividend_payout: "Payout Ratio",
    beta: "Beta",
    book_value_per_share: "Book Value/Share",
    analyst_rating: "Analyst Rating",
    trading_range_12m: "52W Range %",
    eps_growth_this_year: "EPS Growth (YoY)",
    eps_growth_next_year: "EPS Growth (QoQ)",
    projected_earnings_growth: "Revenue Growth",
  }

  function formatMetricValue(key: string, val: number): string {
    if (PCT_METRICS.has(key)) return `${val.toFixed(1)}%`
    return val.toFixed(2)
  }

  // Extract numeric metrics for the sidebar, filtering out non-numeric fields
  const numericMetrics = metrics
    ? Object.entries(metrics).filter(
        ([key, val]) =>
          typeof val === "number" &&
          !SKIP_FIELDS.has(key)
      )
    : []

  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-4">
      {/* Metrics sidebar — appears first on narrow screens */}
      {numericMetrics.length > 0 && (
        <aside className="order-first lg:order-last lg:col-span-1">
          <div className="rounded-xl border border-gray-200 bg-white p-5">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                Key Metrics
              </h2>
              <button
                onClick={refreshMetrics}
                disabled={refreshing}
                className="rounded p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600 disabled:opacity-50"
                title="Refresh from Yahoo Finance"
              >
                <svg className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </button>
            </div>
            {lastUpdated && (
              <p className="mb-3 text-xs text-gray-400">
                Updated {new Date(lastUpdated).toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </p>
            )}
            <dl className="space-y-3">
              {numericMetrics.map(([key, val]) => {
                const color: TrafficColor =
                  typeof val === "number" && thresholds
                    ? getTrafficColor(key, val, thresholds.directions, thresholds.thresholds)
                    : "gray"
                return (
                  <div key={key}>
                    <dt className="text-xs text-gray-500">
                      {METRIC_LABELS[key] || key.replace(/_/g, " ")}
                    </dt>
                    <dd className={`flex items-center gap-1.5 text-sm font-medium tabular-nums ${COLOR_CLASSES[color]}`}>
                      <span className={DOT_CLASSES[color]} aria-hidden="true">●</span>
                      {typeof val === "number" ? formatMetricValue(key, val) : "--"}
                    </dd>
                  </div>
                )
              })}
            </dl>
          </div>
        </aside>
      )}

      {/* Main report */}
      <div
        className={
          numericMetrics.length > 0 ? "lg:col-span-3" : "lg:col-span-4"
        }
      >
        <ResearchReport
          ticker={report.stock_ticker}
          reportContent={
            report.report_content as Record<string, string | Record<string, string>>
          }
          sources={
            report.sources as {
              filing_url?: string
              news_articles?: Array<{ title: string; url: string }>
            }
          }
          createdAt={report.created_at}
        />
      </div>
    </div>
  )
}
