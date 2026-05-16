"use client"

import { useState } from "react"

interface MetricThreshold {
  min: number | null
  max: number | null
}

interface MetricConfigProps {
  overrides: Record<string, MetricThreshold>
  onChange: (overrides: Record<string, MetricThreshold>) => void
}

export const METRIC_LABELS: Record<string, string> = {
  pe_ratio: "P/E Ratio",
  peg_ratio: "PEG Ratio",
  pb_ratio: "P/B Ratio",
  ps_ratio: "P/S Ratio",
  price_to_fcf: "Price to Free Cash Flow",
  roe: "Return on Equity (%)",
  roa: "Return on Assets (%)",
  current_ratio: "Current Ratio",
  debt_to_equity: "Debt to Equity",
  debt_to_ebitda: "Debt to EBITDA",
  gross_margin: "Gross Margin (%)",
  net_profit_margin: "Net Profit Margin (%)",
  dividend_yield: "Dividend Yield (%)",
  dividend_payout: "Dividend Payout (%)",
  beta: "Beta",
  book_value_per_share: "Book Value per Share",
  projected_earnings_growth: "Projected Earnings Growth (%)",
  analyst_rating: "Analyst Rating (1-5)",
  trading_range_12m: "12-Month Trading Range (%)",
}

export default function MetricConfig({
  overrides,
  onChange,
}: MetricConfigProps) {
  const [expanded, setExpanded] = useState(false)

  function updateMetric(
    key: string,
    field: "min" | "max",
    raw: string
  ) {
    const value = raw === "" ? null : parseFloat(raw)
    const updated = {
      ...overrides,
      [key]: { ...overrides[key], [field]: value },
    }
    onChange(updated)
  }

  function hasError(metric: MetricThreshold): boolean {
    if (metric.min !== null && metric.max !== null) {
      return metric.min > metric.max
    }
    return false
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-gray-900"
      >
        <svg
          className={`h-4 w-4 transition-transform ${expanded ? "rotate-90" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M8.25 4.5l7.5 7.5-7.5 7.5"
          />
        </svg>
        Metric Thresholds
      </button>

      {expanded && (
        <div className="mt-4 space-y-3">
          {Object.entries(overrides).map(([key, metric]) => {
            const error = hasError(metric)
            return (
              <div key={key} className="rounded-lg border border-gray-200 bg-white p-4">
                <label className="mb-2 block text-sm font-medium text-gray-700">
                  {METRIC_LABELS[key] || key}
                </label>
                <div className="flex items-center gap-4">
                  <div className="flex-1">
                    <label className="mb-1 block text-xs text-gray-500">
                      Min
                    </label>
                    <input
                      type="number"
                      step="any"
                      value={metric.min ?? ""}
                      onChange={(e) => updateMetric(key, "min", e.target.value)}
                      placeholder="No min"
                      className={`w-full rounded-md border px-3 py-1.5 text-sm ${
                        error
                          ? "border-red-300 focus:border-red-500 focus:ring-red-500"
                          : "border-gray-300 focus:border-blue-500 focus:ring-blue-500"
                      }`}
                    />
                  </div>
                  <span className="mt-5 text-gray-400">-</span>
                  <div className="flex-1">
                    <label className="mb-1 block text-xs text-gray-500">
                      Max
                    </label>
                    <input
                      type="number"
                      step="any"
                      value={metric.max ?? ""}
                      onChange={(e) => updateMetric(key, "max", e.target.value)}
                      placeholder="No max"
                      className={`w-full rounded-md border px-3 py-1.5 text-sm ${
                        error
                          ? "border-red-300 focus:border-red-500 focus:ring-red-500"
                          : "border-gray-300 focus:border-blue-500 focus:ring-blue-500"
                      }`}
                    />
                  </div>
                </div>
                {error && (
                  <p className="mt-1.5 text-xs text-red-600">
                    Min cannot be greater than max
                  </p>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
