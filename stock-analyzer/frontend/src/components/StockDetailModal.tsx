"use client"

import { useEffect, useRef } from "react"
import { useFocusTrap } from "@/hooks/useFocusTrap"
import MetricBadge from "./metric-badge"

export interface StockDetail {
  id: number
  stock_ticker: string
  composite_score: number
  metric_snapshot: Record<string, unknown>
  conviction_data: Record<string, number>
  summary: string | null
  stage?: string
}

interface StockDetailModalProps {
  stock: StockDetail
  onClose: () => void
  triggerRef?: React.RefObject<HTMLElement | null>
}

function scoreColor(score: number): string {
  if (score >= 70) return "text-green-700 bg-green-50 border-green-200"
  if (score >= 40) return "text-yellow-700 bg-yellow-50 border-yellow-200"
  return "text-red-700 bg-red-50 border-red-200"
}

export default function StockDetailModal({ stock, onClose, triggerRef }: StockDetailModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null)
  useFocusTrap(dialogRef, true)

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
        className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-xl bg-white p-6 shadow-xl"
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
            ⚠ Limited data: {Object.keys(dataWarnings).map(k => k.replace(/_/g, " ")).join(", ")} unavailable (free tier)
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
          <p className="text-sm leading-relaxed text-gray-600">
            {stock.summary}
          </p>
        )}
      </div>
    </div>
  )
}
