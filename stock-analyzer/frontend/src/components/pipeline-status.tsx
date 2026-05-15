interface PipelineStatusProps {
  screened: number
  researching: number
  researched: number
  rejected: number
}

const STAGES: { key: keyof PipelineStatusProps; label: string; color: string }[] = [
  { key: "screened", label: "Screened", color: "bg-blue-100 text-blue-800" },
  { key: "researching", label: "Researching", color: "bg-yellow-100 text-yellow-800" },
  { key: "researched", label: "Researched", color: "bg-green-100 text-green-800" },
  { key: "rejected", label: "Rejected", color: "bg-gray-100 text-gray-600" },
]

export default function PipelineStatus(props: PipelineStatusProps) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      {STAGES.map(({ key, label, color }) => (
        <div
          key={key}
          className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${color}`}
        >
          <span>{label}</span>
          <span className="tabular-nums">{props[key]}</span>
        </div>
      ))}
    </div>
  )
}
