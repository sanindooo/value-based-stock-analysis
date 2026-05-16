import { NextRequest, NextResponse } from "next/server"

export const dynamic = "force-dynamic"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

export async function POST(
  _request: NextRequest,
  { params }: { params: Promise<{ runId: string }> }
) {
  const { runId } = await params
  const res = await fetch(
    `${BACKEND_URL}/api/screening/runs/${runId}/recompute`,
    { method: "POST", cache: "no-store" }
  )
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}
