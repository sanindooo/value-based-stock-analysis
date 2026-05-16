import OpinionBadge from "./opinion-badge"
import SourceLinks from "./source-links"

interface ReportContent {
  company_overview?: string
  competitive_position?: string
  financial_health?: string
  growth_trajectory?: string
  key_risks?: string
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
}: ResearchReportProps) {
  const opinion = reportContent.investment_opinion || {}

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3">
          <a
            href="/research"
            className="text-sm text-gray-400 hover:text-gray-600"
          >
            Research
          </a>
          <span className="text-sm text-gray-300">/</span>
          <h1 className="text-2xl font-bold text-gray-900">{ticker}</h1>
        </div>
        <p className="mt-1 text-sm text-gray-500">
          Report generated{" "}
          {new Date(createdAt).toLocaleDateString("en-US", {
            year: "numeric",
            month: "long",
            day: "numeric",
          })}
        </p>
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
