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
}

function scoreColor(score: number): string {
  if (score >= 70) return "text-green-700 bg-green-50"
  if (score >= 40) return "text-yellow-700 bg-yellow-50"
  return "text-red-700 bg-red-50"
}

export default function StockListRow({ stock, onClick }: StockListRowProps) {
  const metrics = stock.metric_snapshot || {}
  const companyName = metrics.company_name as string | undefined
  const sector = metrics.sector as string | undefined
  const dataWarnings = metrics.data_warnings as Record<string, unknown> | undefined
  const hasWarnings = dataWarnings && Object.keys(dataWarnings).length > 0
  const isExceptional = stock.composite_score >= 80

  return (
    <button
      onClick={onClick}
      className={`flex w-full items-center gap-4 border-b px-4 py-3 text-left transition-colors hover:bg-gray-50 ${
        isExceptional ? "border-b-amber-400" : "border-b-gray-100"
      }`}
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
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
          {companyName && (
            <span className="truncate text-sm text-gray-500">{companyName}</span>
          )}
        </div>
        {sector && (
          <span className="text-xs text-gray-400">{sector}</span>
        )}
      </div>
      <div
        className={`flex h-8 w-10 shrink-0 items-center justify-center rounded-md text-sm font-bold tabular-nums ${scoreColor(stock.composite_score)}`}
      >
        {stock.composite_score.toFixed(0)}
      </div>
      <svg className="h-4 w-4 shrink-0 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
      </svg>
    </button>
  )
}
