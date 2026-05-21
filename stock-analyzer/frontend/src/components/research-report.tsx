import Link from "next/link"
import OpinionBadge from "./opinion-badge"
import SourceLinks from "./source-links"

interface ReportContent {
  company_overview?: string
  competitive_position?: string
  financial_health?: string
  growth_trajectory?: string
  key_risks?: string
  pricing_power_durability?: string
  dividend_sustainability_under_stress?: string
  inflation_resilience_assessment?: string
  competitive_moat_strength?: string
  investment_opinion?: {
    verdict?: string
    confidence?: string
    reasoning?: string
  }
}

interface Sources {
  filing_url?: string
  news_articles?: Array<{ title: string; url: string }>
}

interface ResearchReportProps {
  ticker: string
  reportContent: ReportContent
  sources: Sources
  createdAt: string
  mode?: string
}

function Section({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <section className="mb-8">
      <h2 className="mb-3 text-lg font-semibold text-gray-900">
        {title}
      </h2>
      {children}
    </section>
  )
}

export default function ResearchReport({
  ticker,
  reportContent,
  sources,
  createdAt,
  mode = "value",
}: ResearchReportProps) {
  const opinion = reportContent.investment_opinion || {}

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3">
          <Link
            href="/research"
            className="text-sm text-gray-400 hover:text-gray-600"
          >
            Research
          </Link>
          <span className="text-sm text-gray-300">/</span>
          <h1 className="text-2xl font-bold text-gray-900">{ticker}</h1>
        </div>
        <div className="mt-1 flex items-center gap-2">
          <p className="text-sm text-gray-500">
            Report generated{" "}
            {new Date(createdAt).toLocaleDateString("en-US", {
              year: "numeric",
              month: "long",
              day: "numeric",
            })}
          </p>
          <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${
            mode === "preservation"
              ? "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200"
              : "bg-blue-100 text-blue-800 ring-1 ring-blue-200"
          }`}>
            {mode === "preservation" ? "Value + Preservation" : "Value"}
          </span>
        </div>
      </div>

      {/* Investment Opinion — prominent at top */}
      {opinion.verdict && opinion.confidence && (
        <div className="mb-8 rounded-xl border border-gray-200 bg-white p-6">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">
            Investment Opinion
          </h2>
          <OpinionBadge
            verdict={opinion.verdict}
            confidence={opinion.confidence}
            size="lg"
          />
          {opinion.reasoning && (
            <p className="mt-4 text-sm leading-relaxed text-gray-700">
              {opinion.reasoning}
            </p>
          )}
        </div>
      )}

      {/* Report body */}
      <div className="rounded-xl border border-gray-200 bg-white p-6">
        {reportContent.company_overview && (
          <Section title="Company Overview">
            <p className="text-sm leading-relaxed text-gray-700">
              {reportContent.company_overview}
            </p>
          </Section>
        )}

        {reportContent.competitive_position && (
          <Section title="Competitive Position">
            <p className="text-sm leading-relaxed text-gray-700">
              {reportContent.competitive_position}
            </p>
          </Section>
        )}

        {reportContent.financial_health && (
          <Section title="Financial Health Assessment">
            <p className="text-sm leading-relaxed text-gray-700">
              {reportContent.financial_health}
            </p>
          </Section>
        )}

        {reportContent.growth_trajectory && (
          <Section title="Growth Trajectory">
            <p className="text-sm leading-relaxed text-gray-700">
              {reportContent.growth_trajectory}
            </p>
          </Section>
        )}

        {reportContent.key_risks && (
          <Section title="Key Risks">
            <p className="text-sm leading-relaxed text-gray-700">
              {reportContent.key_risks}
            </p>
          </Section>
        )}

        {/* Preservation-specific sections */}
        {reportContent.pricing_power_durability && (
          <Section title="Pricing Power Durability">
            <p className="text-sm leading-relaxed text-gray-700">
              {reportContent.pricing_power_durability}
            </p>
          </Section>
        )}

        {reportContent.dividend_sustainability_under_stress && (
          <Section title="Dividend Sustainability Under Stress">
            <p className="text-sm leading-relaxed text-gray-700">
              {reportContent.dividend_sustainability_under_stress}
            </p>
          </Section>
        )}

        {reportContent.inflation_resilience_assessment && (
          <Section title="Inflation Resilience Assessment">
            <p className="text-sm leading-relaxed text-gray-700">
              {reportContent.inflation_resilience_assessment}
            </p>
          </Section>
        )}

        {reportContent.competitive_moat_strength && (
          <Section title="Competitive Moat Strength">
            <p className="text-sm leading-relaxed text-gray-700">
              {reportContent.competitive_moat_strength}
            </p>
          </Section>
        )}
      </div>

      {/* Sources */}
      <div className="mt-8 rounded-xl border border-gray-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">
          Sources
        </h2>
        <SourceLinks sources={sources} />
      </div>
    </div>
  )
}
