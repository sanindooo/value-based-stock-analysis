"use client"

export interface StockListItem {
  id: number
  stock_ticker: string
  composite_score: number
  metric_snapshot: Record<string, unknown>
  conviction_data: Record<string, number>
  summary: string | null
  stage?: string
}

interface StockListRowProps {
  stock: StockListItem
  onClick: () => void
  selected?: boolean
  onToggle?: (id: number) => void
  researchStatus?: string
  onResearch?: () => void
  onReject?: () => void
  onUnreject?: () => void
}

function scoreColor(score: number): string {
  if (score >= 70) return "text-green-700 bg-green-50"
  if (score >= 40) return "text-yellow-700 bg-yellow-50"
  return "text-red-700 bg-red-50"
}

const KEY_METRICS: { key: string; label: string; suffix?: string }[] = [
  { key: "pe_ratio", label: "P/E" },
  { key: "projected_earnings_growth", label: "EG", suffix: "%" },
  { key: "peg_ratio", label: "PEG" },
  { key: "beta", label: "Beta" },
  { key: "book_value_per_share", label: "BV" },
  { key: "current_ratio", label: "CR" },
  { key: "debt_to_equity", label: "D/E" },
]

function formatMetric(val: unknown, suffix?: string): string {
  if (typeof val !== "number") return "--"
  return `${val.toFixed(1)}${suffix || ""}`
}

export default function StockListRow({ stock, onClick, selected, onToggle, researchStatus, onResearch, onReject, onUnreject }: StockListRowProps) {
  const metrics = stock.metric_snapshot || {}
  const companyName = metrics.company_name as string | undefined
  const sector = metrics.sector as string | undefined
  const dataWarnings = metrics.data_warnings as Record<string, unknown> | undefined
  const hasWarnings = dataWarnings && Object.keys(dataWarnings).length > 0
  const isExceptional = stock.composite_score >= 80

  const actionContent = (() => {
    if (stock.stage === "rejected" && onUnreject) {
      return (
        <button
          onClick={(e) => { e.stopPropagation(); onUnreject(); }}
          className="rounded-lg border border-gray-200 px-2 py-1 text-xs font-medium text-gray-600 hover:bg-gray-50"
        >
          Un-reject
        </button>
      )
    }
    if (stock.stage === "researching") {
      if (researchStatus === "loading") {
        return (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-blue-600">
            <span className="h-3 w-3 animate-spin rounded-full border-2 border-blue-200 border-t-blue-600" />
            Starting...
          </span>
        )
      }
      if (researchStatus === "started") {
        return (
          <a href={`/research/${stock.stock_ticker}`} className="text-xs font-medium text-green-600 hover:underline">
            View progress
          </a>
        )
      }
      if (researchStatus === "failed" && onResearch) {
        return (
          <button
            onClick={(e) => { e.stopPropagation(); onResearch(); }}
            className="rounded-lg border border-red-200 px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50"
          >
            Retry
          </button>
        )
      }
      if (onResearch) {
        return (
          <button
            onClick={(e) => { e.stopPropagation(); onResearch(); }}
            className="rounded-lg border border-blue-200 px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50"
          >
            Retry
          </button>
        )
      }
    }
    if (stock.stage === "researched") {
      return (
        <a
          href={`/research/${stock.stock_ticker}`}
          onClick={(e) => e.stopPropagation()}
          className="text-xs font-medium text-green-700 hover:underline"
        >
          View report
        </a>
      )
    }
    if (stock.stage === "screened" || !stock.stage) {
      return (
        <div className="flex items-center gap-1.5">
          {onResearch && (
            <button
              onClick={(e) => { e.stopPropagation(); onResearch(); }}
              className="rounded-lg border border-blue-200 px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50"
            >
              Research
            </button>
          )}
          {onReject && (
            <button
              onClick={(e) => { e.stopPropagation(); onReject(); }}
              className="rounded-lg border border-gray-200 px-2 py-1 text-xs font-medium text-gray-500 hover:bg-gray-50"
            >
              Reject
            </button>
          )}
        </div>
      )
    }
    return null
  })()

  return (
    <div
      onClick={onClick}
      className={`flex w-full cursor-pointer items-center gap-4 border-b px-4 py-3 text-left transition-colors hover:bg-gray-50 ${
        selected ? "bg-blue-50" : ""
      } ${isExceptional ? "border-b-amber-400" : "border-b-gray-100"}`}
    >
      {onToggle && (
        <input
          type="checkbox"
          checked={selected ?? false}
          onChange={(e) => { e.stopPropagation(); onToggle(stock.id); }}
          onClick={(e) => e.stopPropagation()}
          aria-label={`Select ${stock.stock_ticker}`}
          className="h-4 w-4 shrink-0 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
        />
      )}
      <div className="min-w-0 flex-shrink-0 w-28">
        <div className="flex items-center gap-1.5">
          <span className="font-semibold text-gray-900">{stock.stock_ticker}</span>
          {isExceptional && (
            <span className="text-amber-500" title="Exceptional score">★</span>
          )}
          {hasWarnings && (
            <span className="text-amber-500" title="Data warnings present">
              <svg className="inline h-3.5 w-3.5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.168 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 6a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 6zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
              </svg>
            </span>
          )}
        </div>
        {companyName ? (
          <span className="block truncate text-xs text-gray-500">{companyName}</span>
        ) : sector ? (
          <span className="text-xs text-gray-400">{sector}</span>
        ) : null}
      </div>

      <div className="hidden flex-1 items-center gap-4 sm:flex">
        {KEY_METRICS.map(({ key, label, suffix }) => (
          <div key={key} className="text-center">
            <span className="block text-xs text-gray-400">{label}</span>
            <span className="text-sm tabular-nums text-gray-700">
              {formatMetric(metrics[key], suffix)}
            </span>
          </div>
        ))}
      </div>

      {stock.stage && (
        <span className={`hidden shrink-0 rounded-full px-2 py-0.5 text-xs font-medium sm:inline-block ${
          stock.stage === "researched" ? "bg-green-50 text-green-700" :
          stock.stage === "researching" ? "bg-blue-50 text-blue-700" :
          stock.stage === "rejected" ? "bg-red-50 text-red-700" :
          "bg-gray-100 text-gray-600"
        }`}>
          {stock.stage}
        </span>
      )}

      <div className="hidden shrink-0 sm:flex">{actionContent}</div>

      <div
        className={`flex h-8 w-10 shrink-0 items-center justify-center rounded-md text-sm font-bold tabular-nums ${scoreColor(stock.composite_score)}`}
      >
        {stock.composite_score.toFixed(0)}
      </div>
      <svg className="h-4 w-4 shrink-0 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
      </svg>
    </div>
  )
}
