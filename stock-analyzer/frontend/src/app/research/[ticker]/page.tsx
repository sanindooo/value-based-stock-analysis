"use client"

import { useCallback, useEffect, useState } from "react"
import { useParams } from "next/navigation"
import { apiFetch } from "@/lib/api"
import ResearchReport from "@/components/research-report"

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

export default function ResearchTickerPage() {
  const params = useParams<{ ticker: string }>()
  const ticker = params.ticker.toUpperCase()

  const [report, setReport] = useState<FullReport | null>(null)
  const [metrics, setMetrics] = useState<Record<string, number | null> | null>(
    null
  )
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

  // Fetch screening metrics for the sidebar
  const fetchMetrics = useCallback(async () => {
    try {
      const runs = await apiFetch<ScreeningRun[]>("/screening")
      if (runs.length === 0) return
      // Use the latest completed run
      const latestRun = runs.find((r) => r.status === "completed")
      if (!latestRun) return
      const data = await apiFetch<ResultsPage>(
        `/screening/${latestRun.id}?limit=200&offset=0&sort_by=composite_score&order=desc`
      )
      const match = data.results.find(
        (r) => r.stock_ticker.toUpperCase() === ticker
      )
      if (match) {
        setMetrics(match.metric_snapshot)
      }
    } catch {
      // Non-critical — sidebar just won't show
    }
  }, [ticker])

  useEffect(() => {
    fetchReport()
    fetchMetrics()
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
        <a
          href="/research"
          className="mt-4 text-sm text-blue-600 hover:underline"
        >
          Back to Research
        </a>
      </div>
    )
  }

  if (!report) return null

  // Extract numeric metrics for the sidebar, filtering out non-numeric fields
  const numericMetrics = metrics
    ? Object.entries(metrics).filter(
        ([key, val]) =>
          typeof val === "number" &&
          key !== "sector" &&
          key !== "company_name"
      )
    : []

  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-4">
      {/* Metrics sidebar — appears first on narrow screens */}
      {numericMetrics.length > 0 && (
        <aside className="order-first lg:order-last lg:col-span-1">
          <div className="rounded-xl border border-gray-200 bg-white p-5">
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">
              Screening Metrics
            </h2>
            <dl className="space-y-3">
              {numericMetrics.map(([key, val]) => (
                <div key={key}>
                  <dt className="text-xs text-gray-500">
                    {key.replace(/_/g, " ")}
                  </dt>
                  <dd className="text-sm font-medium tabular-nums text-gray-900">
                    {typeof val === "number" ? val.toFixed(2) : "--"}
                  </dd>
                </div>
              ))}
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
