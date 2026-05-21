"use client"

import { useCallback, useEffect, useState } from "react"
import { toast } from "sonner"
import SectorSelector from "@/components/sector-selector"
import MetricConfig from "@/components/metric-config"
import { apiFetch } from "@/lib/api"

interface MetricThreshold {
  min: number | null
  max: number | null
}

interface Preferences {
  preferred_sectors: string[]
  risk_tolerance: string
  hold_duration: string
  category_weights: Record<string, number>
  metric_overrides: Record<string, MetricThreshold>
  preservation_enabled: boolean
}

const RISK_OPTIONS = [
  { value: "conservative", label: "Conservative" },
  { value: "moderate", label: "Moderate" },
  { value: "aggressive", label: "Aggressive" },
]

const HOLD_OPTIONS = [
  { value: "1-3y", label: "1-3 Years" },
  { value: "3-5y", label: "3-5 Years" },
  { value: "5y+", label: "5+ Years" },
]

const WEIGHT_LABELS: Record<string, string> = {
  value: "Value",
  growth: "Growth",
  financial_health: "Financial Health",
  profitability: "Profitability",
}

export default function SettingsPage() {
  const [prefs, setPrefs] = useState<Preferences | null>(null)
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      const data = await apiFetch<Preferences>("/preferences")
      setPrefs(data)
    } catch {
      toast.error("Failed to load preferences")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function save() {
    if (!prefs) return
    setSaving(true)
    try {
      const data = await apiFetch<Preferences>("/preferences", {
        method: "PUT",
        body: JSON.stringify(prefs),
      })
      setPrefs(data)
      toast.success("Preferences saved")
    } catch {
      toast.error("Failed to save preferences")
    } finally {
      setSaving(false)
    }
  }

  function updateWeight(key: string, value: number) {
    if (!prefs) return
    setPrefs({
      ...prefs,
      category_weights: { ...prefs.category_weights, [key]: value },
    })
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-sm text-gray-500">Loading preferences...</div>
      </div>
    )
  }

  if (!prefs) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-sm text-red-600">
          Could not load preferences. Check that the backend is running.
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">
          Portfolio Preferences
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          Configure your investment criteria for stock screening and analysis.
        </p>
      </div>

      <div className="space-y-8">
        {/* Sector Preferences */}
        <section className="rounded-xl border border-gray-200 bg-white p-6">
          <h2 className="mb-1 text-base font-semibold text-gray-900">
            Preferred Sectors
          </h2>
          <p className="mb-4 text-sm text-gray-500">
            Select the sectors you want to focus your analysis on. Leave empty to
            include all sectors.
          </p>
          <SectorSelector
            selected={prefs.preferred_sectors}
            onChange={(sectors) =>
              setPrefs({ ...prefs, preferred_sectors: sectors })
            }
          />
        </section>

        {/* Preservation Mode */}
        <section className="rounded-xl border border-gray-200 bg-white p-6">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="mb-1 text-base font-semibold text-gray-900">
                Preservation Mode
              </h2>
              <p className="text-sm text-gray-500">
                Evaluate stocks for inflation resilience — pricing power, dividend
                sustainability, stability, and capital efficiency. When enabled,
                new screening runs will compute preservation scores by default.
              </p>
            </div>
            <button
              role="switch"
              aria-checked={prefs.preservation_enabled}
              onClick={() => setPrefs({ ...prefs, preservation_enabled: !prefs.preservation_enabled })}
              className={`relative mt-1 inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full transition-colors ${
                prefs.preservation_enabled ? "bg-emerald-500" : "bg-gray-200"
              }`}
            >
              <span className={`pointer-events-none inline-block h-5 w-5 translate-y-0.5 rounded-full bg-white shadow transition-transform ${
                prefs.preservation_enabled ? "translate-x-5" : "translate-x-0.5"
              }`} />
            </button>
          </div>
        </section>

        {/* Risk Tolerance */}
        <section className="rounded-xl border border-gray-200 bg-white p-6">
          <h2 className="mb-1 text-base font-semibold text-gray-900">
            Risk Tolerance
          </h2>
          <p className="mb-4 text-sm text-gray-500">
            How much volatility and downside risk are you comfortable with?
          </p>
          <div className="flex gap-3">
            {RISK_OPTIONS.map((opt) => (
              <label
                key={opt.value}
                className={`flex flex-1 cursor-pointer items-center justify-center rounded-lg border px-4 py-3 text-sm font-medium transition-colors ${
                  prefs.risk_tolerance === opt.value
                    ? "border-blue-600 bg-blue-50 text-blue-700"
                    : "border-gray-200 bg-white text-gray-700 hover:border-gray-300 hover:bg-gray-50"
                }`}
              >
                <input
                  type="radio"
                  name="risk_tolerance"
                  value={opt.value}
                  checked={prefs.risk_tolerance === opt.value}
                  onChange={() =>
                    setPrefs({ ...prefs, risk_tolerance: opt.value })
                  }
                  className="sr-only"
                />
                {opt.label}
              </label>
            ))}
          </div>
        </section>

        {/* Hold Duration */}
        <section className="rounded-xl border border-gray-200 bg-white p-6">
          <h2 className="mb-1 text-base font-semibold text-gray-900">
            Hold Duration
          </h2>
          <p className="mb-4 text-sm text-gray-500">
            What is your typical investment horizon?
          </p>
          <div className="flex gap-3">
            {HOLD_OPTIONS.map((opt) => (
              <label
                key={opt.value}
                className={`flex flex-1 cursor-pointer items-center justify-center rounded-lg border px-4 py-3 text-sm font-medium transition-colors ${
                  prefs.hold_duration === opt.value
                    ? "border-blue-600 bg-blue-50 text-blue-700"
                    : "border-gray-200 bg-white text-gray-700 hover:border-gray-300 hover:bg-gray-50"
                }`}
              >
                <input
                  type="radio"
                  name="hold_duration"
                  value={opt.value}
                  checked={prefs.hold_duration === opt.value}
                  onChange={() =>
                    setPrefs({ ...prefs, hold_duration: opt.value })
                  }
                  className="sr-only"
                />
                {opt.label}
              </label>
            ))}
          </div>
        </section>

        {/* Category Weights */}
        <section className="rounded-xl border border-gray-200 bg-white p-6">
          <h2 className="mb-1 text-base font-semibold text-gray-900">
            Category Weights
          </h2>
          <p className="mb-4 text-sm text-gray-500">
            Adjust how much each category influences the overall stock score.
          </p>
          <div className="space-y-4">
            {Object.entries(prefs.category_weights).map(([key, weight]) => (
              <div key={key}>
                <div className="mb-1 flex items-center justify-between">
                  <label className="text-sm font-medium text-gray-700">
                    {WEIGHT_LABELS[key] || key}
                  </label>
                  <span className="text-sm tabular-nums text-gray-500">
                    {weight}
                  </span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={weight}
                  onChange={(e) => updateWeight(key, parseInt(e.target.value))}
                  className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-gray-200 accent-blue-600"
                />
              </div>
            ))}
          </div>
        </section>

        {/* Metric Overrides */}
        <section className="rounded-xl border border-gray-200 bg-white p-6">
          <h2 className="mb-1 text-base font-semibold text-gray-900">
            Metric Overrides
          </h2>
          <p className="mb-4 text-sm text-gray-500">
            Fine-tune the threshold for each financial metric used in screening.
            Defaults follow Buffett-style value investing criteria.
          </p>
          <MetricConfig
            overrides={prefs.metric_overrides}
            onChange={(metric_overrides) =>
              setPrefs({ ...prefs, metric_overrides })
            }
          />
        </section>

        {/* Save */}
        <div className="flex items-center justify-end gap-4 pb-8">
          <button
            onClick={save}
            disabled={saving}
            className="rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save Preferences"}
          </button>
        </div>
      </div>
    </div>
  )
}
