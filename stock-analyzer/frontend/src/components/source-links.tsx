interface Sources {
  filing_url?: string
  news_articles?: Array<{ title: string; url: string }>
}

interface SourceLinksProps {
  sources: Sources
}

export default function SourceLinks({ sources }: SourceLinksProps) {
  const hasFilingUrl = !!sources.filing_url
  const hasNews =
    Array.isArray(sources.news_articles) && sources.news_articles.length > 0

  if (!hasFilingUrl && !hasNews) {
    return (
      <p className="text-sm text-gray-400">No sources available.</p>
    )
  }

  return (
    <div className="space-y-4">
      {hasFilingUrl && (
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
            SEC Filing
          </h4>
          <a
            href={sources.filing_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-700 hover:underline"
          >
            <svg
              className="h-4 w-4 shrink-0"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
              />
            </svg>
            10-K / 10-Q Filing on SEC EDGAR
          </a>
        </div>
      )}

      {hasNews && (
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
            News Articles
          </h4>
          <ul className="space-y-2">
            {sources.news_articles!.map((article, idx) => (
              <li key={idx}>
                <a
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 hover:underline"
                >
                  <svg
                    className="h-3.5 w-3.5 shrink-0"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                    />
                  </svg>
                  {article.title}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
