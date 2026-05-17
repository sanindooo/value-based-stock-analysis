import Link from "next/link"

interface PipelineViewProps {
  screened: number
  researching: number
  researched: number
}

const STAGES: {
  key: keyof PipelineViewProps
  label: string
  href: string
  color: string
  activeColor: string
}[] = [
  {
    key: "screened",
    label: "Screened",
    href: "/screening",
    color: "bg-gray-100 text-gray-600 border-gray-200",
    activeColor: "bg-blue-50 text-blue-800 border-blue-200",
  },
  {
    key: "researching",
    label: "Researching",
    href: "/research",
    color: "bg-gray-100 text-gray-600 border-gray-200",
    activeColor: "bg-yellow-50 text-yellow-800 border-yellow-200",
  },
  {
    key: "researched",
    label: "Researched",
    href: "/research",
    color: "bg-gray-100 text-gray-600 border-gray-200",
    activeColor: "bg-green-50 text-green-800 border-green-200",
  },
]

export default function PipelineView(props: PipelineViewProps) {
  return (
    <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
      {STAGES.map((stage, idx) => {
        const count = props[stage.key]
        const isActive = count > 0
        return (
          <div key={stage.key} className="flex items-center gap-1.5 sm:gap-2">
            {idx > 0 && (
              <svg
                className="h-4 w-4 text-gray-300"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 5l7 7-7 7"
                />
              </svg>
            )}
            <Link
              href={stage.href}
              className={`inline-flex items-center gap-1 rounded-lg border px-2 py-1.5 text-xs font-medium transition-colors hover:opacity-80 sm:gap-1.5 sm:px-3 sm:py-2 sm:text-sm ${
                isActive ? stage.activeColor : stage.color
              }`}
            >
              <span>{stage.label}</span>
              <span className="tabular-nums">{count}</span>
            </Link>
          </div>
        )
      })}
    </div>
  )
}
