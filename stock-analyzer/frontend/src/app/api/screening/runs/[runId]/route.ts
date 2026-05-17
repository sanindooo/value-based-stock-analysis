import { NextRequest, NextResponse } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export const dynamic = "force-dynamic"

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ runId: string }> }
) {
  const { runId } = await params
  const res = await backendFetch(`/api/screening/runs/${runId}`, {
    headers: { "Content-Type": "application/json" },
  })
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}

export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ runId: string }> }
) {
  const { runId } = await params
  const res = await backendFetch(`/api/screening/runs/${runId}`, {
    method: "DELETE",
  })
  if (res.status === 204) {
    return new NextResponse(null, { status: 204 })
  }
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}
