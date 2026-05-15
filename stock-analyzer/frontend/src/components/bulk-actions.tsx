"use client"

interface BulkActionsProps {
  selectedCount: number
  onResearch: () => void
  onReject: () => void
}

export default function BulkActions({
  selectedCount,
  onResearch,
  onReject,
}: BulkActionsProps) {
  if (selectedCount === 0) return null

  return (
    <div className="fixed inset-x-0 bottom-0 z-50 border-t border-gray-200 bg-white shadow-lg">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
        <span className="text-sm font-medium text-gray-700">
          {selectedCount} selected
        </span>
        <div className="flex gap-3">
          <button
            onClick={onReject}
            className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50"
          >
            Reject
          </button>
          <button
            onClick={onResearch}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
          >
            Research these
          </button>
        </div>
      </div>
    </div>
  )
}
