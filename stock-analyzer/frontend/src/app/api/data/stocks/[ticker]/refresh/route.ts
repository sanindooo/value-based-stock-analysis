import { NextRequest, NextResponse } from "next/server"

export const dynamic = "force-dynamic"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

export async function POST(
  _request: NextRequest,
  { params }: { params: Promise<{ ticker: string }> }
) {
  const { ticker } = await params
  const res = await fetch(
    `${BACKEND_URL}/api/data/stocks/${ticker}/refresh`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    }
  )
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}
