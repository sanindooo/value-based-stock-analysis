"use client"

import MetricBadge from "./metric-badge"

export interface StockResult {
  id: number
  screening_run_id: number
  stock_ticker: string
  composite_score: number
  metric_snapshot: Record<string, number | null>
  conviction_data: Record<string, number>
  summary: string | null
  stage: string
}

interface StockCardProps {
  stock: StockResult
  selected: boolean
  onToggle: (id: number) => void
  action?: React.ReactNode
}

function scoreColor(score: number): string {
  if (score >= 70) return "text-green-700 bg-green-50 border-green-200"
  if (score >= 40) return "text-yellow-700 bg-yellow-50 border-yellow-200"
  return "text-red-700 bg-red-50 border-red-200"
}

function sectorBadge(sector: string | undefined): string {
  if (!sector) return "bg-gray-100 text-gray-600"
  return "bg-indigo-50 text-indigo-700"
}

export default function StockCard({ stock, selected, onToggle, action }: StockCardProps) {
  const metrics = stock.metric_snapshot || {}
  const conviction = stock.conviction_data || {}
  const sector = metrics.sector as unknown as string | undefined
  const companyName = metrics.company_name as unknown as string | undefined

  // Get top 5 metrics by conviction percentage (excluding non-numeric fields)
  const metricEntries = Object.entries(conviction)
    .filter(([key]) => key !== "composite_score")
    .sort(([, a], [, b]) => b - a)
    .slice(0, 5)

  const isRejected = stock.stage === "rejected"

  return (
    <div
      className={`relative rounded-xl border bg-white p-5 transition-shadow hover:shadow-md ${
        selected ? "border-blue-400 ring-2 ring-blue-100" : "border-gray-200"
      } ${isRejected ? "opacity-60" : ""}`}
    >
      {/* Header */}
      <div className="mb-3 flex items-start justify-between">
        <div className="flex items-start gap-3">
          <input
            type="checkbox"
            checked={selected}
            onChange={() => onToggle(stock.id)}
            aria-label={`Select ${stock.stock_ticker}`}
            className="mt-1 h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <div>
            <h3 className="text-lg font-bold text-gray-900">
              {stock.stock_ticker}
            </h3>
            {companyName && (
              <p className="text-sm text-gray-500">{companyName}</p>
            )}
            <div className="mt-1 flex flex-wrap gap-1.5">
              {sector && (
                <span
                  className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${sectorBadge(sector)}`}
                >
                  {sector}
                </span>
              )}
              {stock.stage !== "screened" && (
                <span
                  className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                    stock.stage === "researching"
                      ? "bg-yellow-50 text-yellow-700"
                      : stock.stage === "researched"
                        ? "bg-green-50 text-green-700"
                        : "bg-gray-100 text-gray-600"
                  }`}
                >
                  {stock.stage}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Composite score */}
        <div
          className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-lg border text-base font-bold tabular-nums ${scoreColor(stock.composite_score)}`}
          aria-label={`Composite score: ${stock.composite_score.toFixed(0)}`}
        >
          {stock.composite_score.toFixed(0)}
        </div>
      </div>

      {/* Metrics with conviction bars */}
      {metricEntries.length > 0 && (
        <div className="mb-3 space-y-2">
          {metricEntries.map(([key, pct]) => (
            <MetricBadge
              key={key}
              name={key}
              value={metrics[key] ?? null}
              convictionPct={pct}
            />
          ))}
        </div>
      )}

      {/* Summary */}
      {stock.summary && (
        <p className="text-xs leading-relaxed text-gray-600">
          {stock.summary}
        </p>
      )}

      {action && <div className="mt-3">{action}</div>}
    </div>
  )
}
