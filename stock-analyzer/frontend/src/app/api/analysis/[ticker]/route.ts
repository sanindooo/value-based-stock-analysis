import { NextRequest, NextResponse } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ ticker: string }> }
) {
  const { ticker } = await params
  if (!/^[A-Z0-9.\-]{1,10}$/i.test(ticker)) {
    return NextResponse.json({ error: "Invalid ticker" }, { status: 400 })
  }
  const poll = request.nextUrl.searchParams.get("poll")

  try {
    const res = await backendFetch(`/api/analysis/${ticker}`, {
      cache: poll ? "no-store" : "force-cache",
      ...(poll ? {} : { next: { tags: [`analysis-${ticker}`], revalidate: 300 } }),
      headers: { "Content-Type": "application/json" },
    })
    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch {
    return NextResponse.json({ error: "Backend unavailable" }, { status: 502 })
  }
}
