"use client"

interface SkeletonProps {
  className?: string
}

export function SkeletonLine({ className = "" }: SkeletonProps) {
  return <div className={`animate-pulse rounded bg-gray-200 ${className}`} />
}

export function SkeletonCard() {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5">
      <div className="mb-3 flex items-start justify-between">
        <div className="space-y-2">
          <SkeletonLine className="h-5 w-20" />
          <SkeletonLine className="h-3 w-32" />
        </div>
        <SkeletonLine className="h-12 w-12 rounded-lg" />
      </div>
      <div className="space-y-2">
        <SkeletonLine className="h-3 w-full" />
        <SkeletonLine className="h-3 w-4/5" />
        <SkeletonLine className="h-3 w-3/5" />
      </div>
    </div>
  )
}

export function SkeletonListRow() {
  return (
    <div className="flex items-center gap-4 border-b border-gray-100 px-4 py-3">
      <div className="flex-1 space-y-1.5">
        <SkeletonLine className="h-4 w-24" />
        <SkeletonLine className="h-3 w-16" />
      </div>
      <SkeletonLine className="h-8 w-10 rounded-md" />
    </div>
  )
}

export function SkeletonRunCard() {
  return (
    <div className="flex items-center justify-between rounded-xl border border-gray-200 bg-white px-5 py-4">
      <div className="space-y-1.5">
        <SkeletonLine className="h-4 w-20" />
        <SkeletonLine className="h-3 w-28" />
      </div>
      <div className="flex items-center gap-4">
        <SkeletonLine className="h-4 w-16" />
        <SkeletonLine className="h-5 w-16 rounded-full" />
      </div>
    </div>
  )
}

export function SkeletonProgress() {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5">
      <div className="mb-3 flex items-center justify-between">
        <SkeletonLine className="h-4 w-32" />
        <SkeletonLine className="h-3 w-12" />
      </div>
      <div className="mb-3 grid grid-cols-3 gap-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="rounded-lg bg-gray-50 px-3 py-2 text-center">
            <SkeletonLine className="mx-auto h-6 w-8" />
            <SkeletonLine className="mx-auto mt-1 h-3 w-12" />
          </div>
        ))}
      </div>
      <div className="space-y-1.5 rounded-lg bg-gray-50 px-3 py-2">
        <SkeletonLine className="h-3 w-full" />
        <SkeletonLine className="h-3 w-4/5" />
        <SkeletonLine className="h-3 w-3/5" />
      </div>
    </div>
  )
}
