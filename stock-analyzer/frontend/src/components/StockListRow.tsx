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

  return (
    <button
      onClick={onClick}
      className="flex w-full items-center gap-4 border-b border-gray-100 px-4 py-3 text-left transition-colors hover:bg-gray-50"
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-gray-900">{stock.stock_ticker}</span>
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
