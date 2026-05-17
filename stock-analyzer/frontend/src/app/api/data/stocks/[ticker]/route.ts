import { NextRequest, NextResponse } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ ticker: string }> }
) {
  const { ticker } = await params
  const { searchParams } = new URL(request.url)
  const qs = searchParams.toString()
  const res = await backendFetch(
    `/api/data/stocks/${ticker}${qs ? `?${qs}` : ""}`,
    {
      cache: "force-cache",
      next: { tags: [`stock-${ticker}`], revalidate: 3600 },
      headers: { "Content-Type": "application/json" },
    }
  )
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}
