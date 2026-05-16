import { NextRequest, NextResponse } from "next/server"

export const dynamic = "force-dynamic"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ runId: string }> }
) {
  const { runId } = await params
  const { searchParams } = new URL(request.url)
  const qs = searchParams.toString()
  const url = `${BACKEND_URL}/api/screening/${runId}/results${qs ? `?${qs}` : ""}`

  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
  })
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ runId: string }> }
) {
  const { runId } = await params
  const body = await request.json()
  const { resultId, stage } = body as { resultId: number; stage: string }

  const res = await fetch(
    `${BACKEND_URL}/api/screening/${runId}/results/${resultId}/stage`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stage }),
    }
  )
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}
