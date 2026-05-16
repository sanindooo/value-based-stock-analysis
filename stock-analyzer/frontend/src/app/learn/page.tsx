export default function LearnPage() {
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-2 text-2xl font-bold text-gray-900">
        Metrics Reference
      </h1>
      <p className="mb-8 text-sm text-gray-500">
        What each screening metric measures, why it matters for value investing, and how to interpret the results.
      </p>

      <section className="mb-10">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">Value Metrics</h2>
        <p className="mb-4 text-sm text-gray-600">
          Value metrics compare a stock&apos;s price to its underlying fundamentals. Lower values suggest the market is pricing the stock cheaply relative to what the company earns, owns, or generates.
        </p>
        <div className="space-y-4">
          <MetricEntry
            name="P/E Ratio (Price-to-Earnings)"
            direction="Lower is better"
            threshold="≤ 20"
            description="How many years of current earnings you're paying for. A P/E of 15 means you pay $15 for every $1 of annual profit. Stocks below 20 are considered reasonably priced by value investors."
          />
          <MetricEntry
            name="PEG Ratio"
            direction="Lower is better"
            threshold="≤ 1.5"
            description="P/E ratio divided by earnings growth rate. Adjusts valuation for growth — a PEG below 1.0 suggests the stock is cheap relative to how fast it's growing."
          />
          <MetricEntry
            name="P/B Ratio (Price-to-Book)"
            direction="Lower is better"
            threshold="≤ 3"
            description="Price relative to the company's net assets (what would be left if you liquidated everything). Below 1.0 means you're buying assets for less than their book value."
          />
          <MetricEntry
            name="Beta"
            direction="Lower is better"
            threshold="≤ 1.5"
            description="How much a stock moves relative to the overall market. A beta of 1.0 moves with the market; below 1.0 is less volatile (preferred by conservative investors)."
          />
          <MetricEntry
            name="Book Value per Share"
            direction="Higher is better"
            threshold="≥ $10"
            description="The company's net asset value divided by shares outstanding. A high book value provides a 'floor' on the stock price — you're buying real assets."
          />
          <MetricEntry
            name="Analyst Rating"
            direction="Higher is better"
            threshold="≥ 3 (out of 5)"
            description="Consensus analyst recommendation, where 5 is Strong Buy and 1 is Strong Sell. Provides a professional consensus view alongside your own analysis."
          />
          <MetricEntry
            name="12-Month Trading Range"
            direction="Lower is better"
            threshold="≤ 50%"
            description="The percentage spread between 52-week high and low. A narrow range suggests price stability; a wide range suggests volatility or recent sharp moves."
          />
        </div>
      </section>

      <section className="mb-10">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">Growth Metrics</h2>
        <p className="mb-4 text-sm text-gray-600">
          Growth metrics measure how fast the company is expanding its earnings and revenue. Value investors want growth, but at a reasonable price.
        </p>
        <div className="space-y-4">
          <MetricEntry
            name="Projected Earnings Growth"
            direction="Higher is better"
            threshold="≥ 5%"
            description="Expected annual earnings growth rate based on analyst consensus. Shows whether the company is expected to grow profits in the coming years."
          />
          <MetricEntry
            name="EPS Growth (This/Next Year)"
            direction="Higher is better"
            threshold="Positive"
            description="Year-over-year earnings per share growth. Positive growth means the company is becoming more profitable on a per-share basis."
          />
          <MetricEntry
            name="Sales Growth (5Y)"
            direction="Higher is better"
            threshold="Positive"
            description="Revenue growth over the past 5 years, annualized. Sustained revenue growth indicates genuine business expansion, not just cost-cutting."
          />
        </div>
      </section>

      <section className="mb-10">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">Financial Health</h2>
        <p className="mb-4 text-sm text-gray-600">
          Financial health metrics assess the company&apos;s balance sheet strength and ability to meet obligations. They reveal whether the company can survive downturns.
        </p>
        <div className="space-y-4">
          <MetricEntry
            name="Current Ratio"
            direction="Higher is better"
            threshold="≥ 1.5"
            description="Short-term assets divided by short-term debts. Above 1.5 means the company can comfortably pay its bills for the next year without borrowing."
          />
          <MetricEntry
            name="Debt-to-Equity"
            direction="Lower is better"
            threshold="≤ 1.0"
            description="Total debt divided by shareholder equity. Below 1.0 means the company owns more than it owes — a sign of conservative financial management."
          />
          <MetricEntry
            name="Debt-to-EBITDA"
            direction="Lower is better"
            threshold="≤ 3.0"
            description="Total debt divided by annual operating earnings. Shows how many years of profits it would take to pay off all debt. Below 3 is healthy for most industries."
          />
        </div>
      </section>

      <section className="mb-10">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">Profitability</h2>
        <p className="mb-4 text-sm text-gray-600">
          Profitability metrics reveal how efficiently the company turns revenue into profit and shareholder value. High margins indicate competitive advantages (moats).
        </p>
        <div className="space-y-4">
          <MetricEntry
            name="ROE (Return on Equity)"
            direction="Higher is better"
            threshold="≥ 15%"
            description="Net profit as a percentage of shareholder equity. Above 15% means management is generating strong returns on the capital investors have entrusted to them."
          />
          <MetricEntry
            name="ROA (Return on Assets)"
            direction="Higher is better"
            threshold="≥ 5%"
            description="Net profit relative to total assets. Shows how effectively the company uses everything it owns to generate profit, regardless of how it's financed."
          />
          <MetricEntry
            name="Net Profit Margin"
            direction="Higher is better"
            threshold="≥ 10%"
            description="What percentage of each dollar of revenue becomes profit after all expenses. High margins suggest pricing power and operational efficiency."
          />
          <MetricEntry
            name="Dividend Yield"
            direction="Higher is better"
            threshold="≥ 1%"
            description="Annual dividend payment as a percentage of stock price. Provides income while you wait for value to be recognized by the market."
          />
          <MetricEntry
            name="Dividend Payout Ratio"
            direction="Lower is better"
            threshold="≤ 60%"
            description="Percentage of earnings paid out as dividends. Below 60% means the dividend is sustainable and the company retains earnings for growth."
          />
        </div>
      </section>
    </div>
  )
}

function MetricEntry({
  name,
  direction,
  threshold,
  description,
}: {
  name: string
  direction: string
  threshold: string
  description: string
}) {
  return (
    <div className="rounded-lg border border-gray-100 bg-white px-4 py-3">
      <div className="mb-1 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900">{name}</h3>
        <div className="flex items-center gap-2">
          <span className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
            {direction}
          </span>
          <span className="rounded bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
            {threshold}
          </span>
        </div>
      </div>
      <p className="text-sm leading-relaxed text-gray-600">{description}</p>
    </div>
  )
}
