import { NextRequest, NextResponse } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ ticker: string }> }
) {
  const { ticker } = await params
  const poll = request.nextUrl.searchParams.get("poll")

  const res = await backendFetch(`/api/analysis/${ticker}`, {
    cache: poll ? "no-store" : "force-cache",
    ...(poll ? {} : { next: { tags: [`analysis-${ticker}`], revalidate: 300 } }),
    headers: { "Content-Type": "application/json" },
  })
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}
