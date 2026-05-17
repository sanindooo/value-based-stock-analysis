import { NextRequest, NextResponse } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export const dynamic = "force-dynamic"

export async function POST(
  _request: NextRequest,
  { params }: { params: Promise<{ ticker: string }> }
) {
  const { ticker } = await params
  const res = await backendFetch(`/api/data/stocks/${ticker}/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  })
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}
