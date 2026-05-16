import ConvictionBar from "./conviction-bar"

interface MetricBadgeProps {
  name: string
  value: number | null
  convictionPct?: number
}

const METRIC_LABELS: Record<string, string> = {
  pe_ratio: "P/E",
  forward_pe: "Fwd P/E",
  pb_ratio: "P/B",
  ps_ratio: "P/S",
  peg_ratio: "PEG",
  price_to_fcf: "P/FCF",
  roe: "ROE",
  roa: "ROA",
  roi: "ROI",
  gross_margin: "Gross Margin",
  operating_margin: "Op Margin",
  net_profit_margin: "Net Margin",
  current_ratio: "Current Ratio",
  debt_to_equity: "D/E",
  debt_to_ebitda: "D/EBITDA",
  eps_growth_next_5y: "EPS Growth 5Y",
  dividend_yield: "Div Yield",
  projected_earnings_growth: "Earnings Growth",
  beta: "Beta",
  book_value_per_share: "Book Value",
  market_cap: "Market Cap",
  composite_score: "Score",
}

function formatValue(name: string, value: number | null): string {
  if (value === null || value === undefined) return "N/A"
  if (name === "book_value_per_share") return `$${value.toFixed(2)}`
  if (name === "market_cap") {
    if (value >= 1e12) return `$${(value / 1e12).toFixed(1)}T`
    if (value >= 1e9) return `$${(value / 1e9).toFixed(1)}B`
    if (value >= 1e6) return `$${(value / 1e6).toFixed(0)}M`
    return `$${value.toFixed(0)}`
  }
  if (
    name.includes("margin") ||
    name.includes("yield") ||
    name.includes("growth") ||
    name === "roe" ||
    name === "roa" ||
    name === "roi"
  ) {
    return `${value.toFixed(1)}%`
  }
  return value.toFixed(2)
}

export default function MetricBadge({
  name,
  value,
  convictionPct,
}: MetricBadgeProps) {
  const label = METRIC_LABELS[name] || name.replace(/_/g, " ")

  if (!convictionPct) {
    return (
      <div className="flex items-baseline justify-between">
        <span className="text-xs font-medium text-gray-700">{label}</span>
        <span className="text-xs tabular-nums text-gray-900">
          {formatValue(name, value)}
        </span>
      </div>
    )
  }

  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between">
        <span className="text-xs font-medium text-gray-700">{label}</span>
        <span className="text-xs tabular-nums text-gray-900">
          {formatValue(name, value)}
        </span>
      </div>
      <ConvictionBar percentage={convictionPct} label={label} />
    </div>
  )
}
