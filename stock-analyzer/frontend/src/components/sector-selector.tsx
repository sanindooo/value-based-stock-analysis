"use client"

const SECTORS = [
  "Technology",
  "Healthcare",
  "Financials",
  "Consumer Discretionary",
  "Consumer Staples",
  "Energy",
  "Industrials",
  "Materials",
  "Real Estate",
  "Utilities",
  "Communication Services",
]

interface SectorSelectorProps {
  selected: string[]
  onChange: (sectors: string[]) => void
}

export default function SectorSelector({
  selected,
  onChange,
}: SectorSelectorProps) {
  function toggle(sector: string) {
    if (selected.includes(sector)) {
      onChange(selected.filter((s) => s !== sector))
    } else {
      onChange([...selected, sector])
    }
  }

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
      {SECTORS.map((sector) => {
        const active = selected.includes(sector)
        return (
          <button
            key={sector}
            type="button"
            onClick={() => toggle(sector)}
            className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
              active
                ? "border-blue-600 bg-blue-50 text-blue-700"
                : "border-gray-200 bg-white text-gray-700 hover:border-gray-300 hover:bg-gray-50"
            }`}
          >
            {sector}
          </button>
        )
      })}
    </div>
  )
}
