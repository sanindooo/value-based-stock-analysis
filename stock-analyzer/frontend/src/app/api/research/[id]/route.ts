import { NextRequest, NextResponse } from "next/server"

export const dynamic = "force-dynamic"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  const { searchParams } = new URL(request.url)
  const type = searchParams.get("type")

  // If type=status, proxy to the task status endpoint
  if (type === "status") {
    const res = await fetch(
      `${BACKEND_URL}/api/research/status/${id}`,
      {
        headers: { "Content-Type": "application/json" },
      }
    )
    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  }

  // Default: proxy to the report endpoint
  const res = await fetch(`${BACKEND_URL}/api/research/${id}`, {
    headers: { "Content-Type": "application/json" },
  })
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}
