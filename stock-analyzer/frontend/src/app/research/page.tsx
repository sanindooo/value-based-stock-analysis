"use client"

import { useCallback, useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"
import OpinionBadge from "@/components/opinion-badge"

interface ReportSummary {
  id: number
  stock_ticker: string
  created_at: string
  verdict: string | null
  confidence: string | null
}

export default function ResearchPage() {
  const [reports, setReports] = useState<ReportSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState<string | null>(null)

  const loadReports = useCallback(async () => {
    try {
      const data = await apiFetch<ReportSummary[]>("/research")
      setReports(data)
    } catch {
      setToast("Failed to load research reports")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadReports()
  }, [loadReports])

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3000)
      return () => clearTimeout(timer)
    }
  }, [toast])

  function formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    })
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-sm text-gray-500">
          Loading research reports...
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Research Reports</h1>
        <p className="mt-1 text-sm text-gray-500">
          Deep-dive research reports with investment opinions and source links.
        </p>
      </div>

      {toast && (
        <div
          className={`mb-4 rounded-lg px-4 py-2 text-sm font-medium ${
            toast.includes("Failed")
              ? "bg-red-50 text-red-600"
              : "bg-green-50 text-green-600"
          }`}
        >
          {toast}
        </div>
      )}

      {reports.length === 0 ? (
        <div className="rounded-xl border border-gray-200 bg-white py-16 text-center">
          <p className="text-sm text-gray-500">
            No research reports yet. Promote stocks from a screening run to
            start research.
          </p>
          <a
            href="/screening"
            className="mt-3 inline-block text-sm font-medium text-blue-600 hover:text-blue-700"
          >
            Go to Screening
          </a>
        </div>
      ) : (
        <div className="space-y-3">
          {reports.map((report) => (
            <a
              key={report.id}
              href={`/research/${report.stock_ticker}`}
              className="flex items-center justify-between rounded-xl border border-gray-200 bg-white px-5 py-4 transition-colors hover:border-gray-300 hover:bg-gray-50"
            >
              <div>
                <p className="text-sm font-medium text-gray-900">
                  {report.stock_ticker}
                </p>
                <p className="text-xs text-gray-500">
                  {formatDate(report.created_at)}
                </p>
              </div>
              <div className="flex items-center gap-4">
                {report.verdict && report.confidence ? (
                  <OpinionBadge
                    verdict={report.verdict}
                    confidence={report.confidence}
                  />
                ) : (
                  <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600">
                    Processing
                  </span>
                )}
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  )
}
