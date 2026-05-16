"use client"

import { useCallback, useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import PipelineView from "@/components/pipeline-view"
import OpinionBadge from "@/components/opinion-badge"

interface Preferences {
  min_market_cap: number | null
  max_pe_ratio: number | null
  [key: string]: unknown
}

interface ScreeningRun {
  id: number
  created_at: string
  status: string
  result_count: number
}

interface ReportSummary {
  id: number
  stock_ticker: string
  created_at: string
  verdict: string | null
  confidence: string | null
}

interface HighlightStock {
  id: number
  stock_ticker: string
  composite_score: number
  metric_snapshot: Record<string, unknown>
  conviction_data: Record<string, number>
  summary: string | null
  stage: string
}

interface StockResult {
  id: number
  stock_ticker: string
  composite_score: number
  metric_snapshot: Record<string, number | null>
  stage: string
}

interface ResultsPage {
  results: StockResult[]
  total: number
}

type DashboardState =
  | "loading"
  | "no-preferences"
  | "no-runs"
  | "no-promoted"
  | "research-active"
  | "reports-complete"

export default function Dashboard() {
  const [state, setState] = useState<DashboardState>("loading")
  const [runs, setRuns] = useState<ScreeningRun[]>([])
  const [reports, setReports] = useState<ReportSummary[]>([])
  const [highlights, setHighlights] = useState<HighlightStock[]>([])
  const [stageCounts, setStageCounts] = useState({
    screened: 0,
    researching: 0,
    researched: 0,
  })

  const load = useCallback(async () => {
    try {
      // Fetch preferences, screening runs, reports, and highlights in parallel
      const [prefs, screeningRuns, researchReports, exceptionalStocks] = await Promise.all([
        apiFetch<Preferences>("/preferences").catch(() => null),
        apiFetch<ScreeningRun[]>("/screening").catch(() => []),
        apiFetch<ReportSummary[]>("/research").catch(() => []),
        apiFetch<HighlightStock[]>("/screening/highlights?min_score=80&limit=5").catch(() => []),
      ])

      setRuns(screeningRuns)
      setReports(researchReports)
      setHighlights(exceptionalStocks)

      // Check if preferences are configured
      const hasPrefs =
        prefs !== null &&
        typeof prefs === "object" &&
        Object.values(prefs).some((v) => v !== null && v !== undefined)

      if (!hasPrefs && screeningRuns.length === 0) {
        setState("no-preferences")
        return
      }

      if (screeningRuns.length === 0) {
        setState("no-runs")
        return
      }

      // Get stage counts from the latest completed run
      const latestRun = screeningRuns.find((r) => r.status === "completed")
      if (latestRun) {
        try {
          const data = await apiFetch<ResultsPage>(
            `/screening/${latestRun.id}?limit=200&offset=0&sort_by=composite_score&order=desc`
          )
          const counts = {
            screened: data.results.filter((r) => r.stage === "screened")
              .length,
            researching: data.results.filter(
              (r) => r.stage === "researching"
            ).length,
            researched: data.results.filter((r) => r.stage === "researched")
              .length,
          }
          setStageCounts(counts)

          // Determine state based on promotion status
          const promoted = counts.researching + counts.researched
          if (promoted === 0 && researchReports.length === 0) {
            setState("no-promoted")
            return
          }
        } catch {
          // Non-critical
        }
      }

      if (researchReports.length > 0) {
        setState("reports-complete")
      } else {
        setState("research-active")
      }
    } catch {
      setState("no-preferences")
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  if (state === "loading") {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-sm text-gray-500">Loading dashboard...</div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">
          Value investing stock screening and research pipeline.
        </p>
      </div>

      {/* No preferences set */}
      {state === "no-preferences" && (
        <div className="rounded-xl border border-gray-200 bg-white py-16 text-center">
          <h2 className="text-base font-semibold text-gray-900">
            Welcome to Stock Analyzer
          </h2>
          <p className="mt-2 text-sm text-gray-500">
            Configure your portfolio preferences to get started.
          </p>
          <a
            href="/settings"
            className="mt-4 inline-block rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-700"
          >
            Configure Preferences
          </a>
        </div>
      )}

      {/* Preferences set but no screening runs */}
      {state === "no-runs" && (
        <div className="rounded-xl border border-gray-200 bg-white py-16 text-center">
          <h2 className="text-base font-semibold text-gray-900">
            Ready to screen
          </h2>
          <p className="mt-2 text-sm text-gray-500">
            Your preferences are set. Run your first screen to find value
            stocks.
          </p>
          <a
            href="/screening"
            className="mt-4 inline-block rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-700"
          >
            Run First Screen
          </a>
        </div>
      )}

      {/* Run complete but no stocks promoted */}
      {state === "no-promoted" && (
        <div className="rounded-xl border border-gray-200 bg-white py-16 text-center">
          <h2 className="text-base font-semibold text-gray-900">
            No stocks promoted to research
          </h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-gray-500">
            Your last screen found candidates but none were promoted to
            research. Review results and promote stocks, or adjust your
            thresholds.
          </p>
          <div className="mt-4 flex items-center justify-center gap-3">
            {runs.length > 0 && (
              <a
                href={`/screening/${runs[0].id}`}
                className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-700"
              >
                View Latest Results
              </a>
            )}
            <a
              href="/settings"
              className="rounded-lg border border-gray-200 bg-white px-5 py-2.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50"
            >
              Adjust Settings
            </a>
          </div>
        </div>
      )}

      {/* Stocks actively in research */}
      {state === "research-active" && (
        <div className="space-y-6">
          <div className="rounded-xl border border-gray-200 bg-white p-6">
            <h2 className="mb-4 text-sm font-semibold text-gray-900">
              Pipeline Progress
            </h2>
            <PipelineView {...stageCounts} />
            <p className="mt-4 text-sm text-gray-500">
              {stageCounts.researching > 0
                ? `${stageCounts.researching} stock${stageCounts.researching === 1 ? "" : "s"} currently being researched.`
                : "Promote stocks from screening to start research."}
            </p>
          </div>

          <div className="flex gap-3">
            <a
              href="/screening"
              className="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50"
            >
              View Screening
            </a>
            <a
              href="/research"
              className="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50"
            >
              View Research
            </a>
          </div>
        </div>
      )}

      {/* Exceptional stocks section — shown when highlights exist */}
      {highlights.length > 0 && state !== "no-preferences" && state !== "no-runs" && (
        <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-5">
          <div className="mb-3 flex items-center gap-2">
            <span className="text-amber-500">★</span>
            <h2 className="text-sm font-semibold text-gray-900">Exceptional Stocks</h2>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {highlights.map((stock) => {
              const companyName = stock.metric_snapshot?.company_name
              return (
                <div
                  key={stock.id}
                  className="flex items-center justify-between rounded-lg border border-amber-200 bg-white px-4 py-3"
                >
                  <div>
                    <p className="text-sm font-semibold text-gray-900">{stock.stock_ticker}</p>
                    {typeof companyName === "string" && (
                      <p className="text-xs text-gray-500">{companyName}</p>
                    )}
                  </div>
                  <span className="rounded-md bg-green-50 px-2 py-0.5 text-sm font-bold tabular-nums text-green-700">
                    {stock.composite_score.toFixed(0)}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Reports complete */}
      {state === "reports-complete" && (
        <div className="space-y-6">
          <div className="rounded-xl border border-gray-200 bg-white p-6">
            <h2 className="mb-4 text-sm font-semibold text-gray-900">
              Pipeline Progress
            </h2>
            <PipelineView {...stageCounts} />
          </div>

          <div>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-900">
                Latest Reports
              </h2>
              <a
                href="/research"
                className="text-sm font-medium text-blue-600 hover:text-blue-700"
              >
                View all
              </a>
            </div>
            <div className="space-y-3">
              {/* Sort by verdict: Buy first, then Hold, then Avoid */}
              {[...reports]
                .sort((a, b) => {
                  const order: Record<string, number> = {
                    buy: 0,
                    hold: 1,
                    avoid: 2,
                  }
                  const aOrder =
                    order[(a.verdict || "").toLowerCase()] ?? 3
                  const bOrder =
                    order[(b.verdict || "").toLowerCase()] ?? 3
                  return aOrder - bOrder
                })
                .slice(0, 5)
                .map((report) => (
                  <a
                    key={report.id}
                    href={`/research/${report.stock_ticker}`}
                    className="flex items-center justify-between rounded-xl border border-gray-200 bg-white px-5 py-4 transition-colors hover:border-gray-300 hover:bg-gray-50"
                  >
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        {report.stock_ticker}
                      </p>
                      <p className="text-xs text-gray-500">
                        {new Date(report.created_at).toLocaleDateString(
                          "en-US",
                          {
                            month: "short",
                            day: "numeric",
                          }
                        )}
                      </p>
                    </div>
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
                  </a>
                ))}
            </div>
          </div>

          <div className="flex gap-3">
            <a
              href="/screening"
              className="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50"
            >
              Run New Screen
            </a>
            <a
              href="/research"
              className="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50"
            >
              All Reports
            </a>
          </div>
        </div>
      )}
    </div>
  )
}
