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
    <div className="flex items-center gap-2">
      {STAGES.map((stage, idx) => {
        const count = props[stage.key]
        const isActive = count > 0
        return (
          <div key={stage.key} className="flex items-center gap-2">
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
            <a
              href={stage.href}
              className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-medium transition-colors hover:opacity-80 ${
                isActive ? stage.activeColor : stage.color
              }`}
            >
              <span>{stage.label}</span>
              <span className="tabular-nums">{count}</span>
            </a>
          </div>
        )
      })}
    </div>
  )
}
