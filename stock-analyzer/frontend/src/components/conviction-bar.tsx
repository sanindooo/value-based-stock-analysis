interface ConvictionBarProps {
  /** How far above/below threshold as a percentage (0-100+). */
  percentage: number
  label: string
}

function getConviction(pct: number): {
  color: string
  bg: string
  text: string
} {
  if (pct >= 30) {
    return {
      color: "bg-green-500",
      bg: "bg-green-50",
      text: "Well above threshold",
    }
  }
  if (pct >= 10) {
    return {
      color: "bg-yellow-500",
      bg: "bg-yellow-50",
      text: "Above threshold",
    }
  }
  return {
    color: "bg-red-400",
    bg: "bg-red-50",
    text: "Barely passing",
  }
}

export default function ConvictionBar({ percentage, label }: ConvictionBarProps) {
  const capped = Math.min(Math.max(percentage, 0), 100)
  const { color, bg, text } = getConviction(percentage)

  return (
    <div className="flex items-center gap-2">
      <span className="w-24 shrink-0 truncate text-xs text-gray-600">
        {label}
      </span>
      <div
        className={`relative h-2 flex-1 overflow-hidden rounded-full ${bg}`}
        role="meter"
        aria-valuenow={capped}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${label}: ${text}`}
      >
        <div
          className={`absolute inset-y-0 left-0 rounded-full ${color}`}
          style={{ width: `${capped}%` }}
        />
      </div>
      <span className="w-20 shrink-0 text-right text-xs text-gray-500">
        {text}
      </span>
    </div>
  )
}
