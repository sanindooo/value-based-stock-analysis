import { NextRequest, NextResponse } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

const VALID_TIERS = new Set(["standard"])

export async function POST(request: NextRequest) {
  const url = new URL(request.url)
  const ticker = url.searchParams.get("ticker")
  const tier = url.searchParams.get("tier") || "standard"

  if (!ticker || !/^[A-Z0-9.\-]{1,10}$/i.test(ticker)) {
    return NextResponse.json({ error: "Invalid ticker" }, { status: 400 })
  }

  if (!VALID_TIERS.has(tier)) {
    return NextResponse.json({ error: `invalid tier: ${tier}` }, { status: 400 })
  }

  try {
    const body = await request.json()
    const res = await backendFetch(`/api/analysis/${tier}/${ticker}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch {
    return NextResponse.json({ error: "Backend unavailable" }, { status: 502 })
  }
}
