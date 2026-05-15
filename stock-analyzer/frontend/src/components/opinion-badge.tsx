interface OpinionBadgeProps {
  verdict: string
  confidence: string
  size?: "sm" | "lg"
}

function verdictStyle(verdict: string): string {
  switch (verdict.toLowerCase()) {
    case "buy":
      return "bg-green-50 text-green-800 border-green-200"
    case "hold":
      return "bg-yellow-50 text-yellow-800 border-yellow-200"
    case "avoid":
      return "bg-red-50 text-red-800 border-red-200"
    default:
      return "bg-gray-100 text-gray-600 border-gray-200"
  }
}

function confidenceLabel(confidence: string): string {
  switch (confidence.toLowerCase()) {
    case "high":
      return "High Confidence"
    case "medium":
      return "Medium Confidence"
    case "low":
      return "Low Confidence"
    default:
      return confidence
  }
}

export default function OpinionBadge({
  verdict,
  confidence,
  size = "sm",
}: OpinionBadgeProps) {
  const isLarge = size === "lg"

  return (
    <div className="flex items-center gap-2">
      <span
        className={`inline-flex items-center rounded-full border font-semibold ${verdictStyle(verdict)} ${
          isLarge ? "px-4 py-1.5 text-base" : "px-2.5 py-0.5 text-xs"
        }`}
      >
        {verdict}
      </span>
      <span
        className={`text-gray-500 ${isLarge ? "text-sm" : "text-xs"}`}
      >
        {confidenceLabel(confidence)}
      </span>
    </div>
  )
}
