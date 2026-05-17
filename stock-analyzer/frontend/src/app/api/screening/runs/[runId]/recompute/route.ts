import { NextRequest, NextResponse } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export const dynamic = "force-dynamic"

export async function POST(
  _request: NextRequest,
  { params }: { params: Promise<{ runId: string }> }
) {
  const { runId } = await params
  const res = await backendFetch(
    `/api/screening/runs/${runId}/recompute`,
    { method: "POST", cache: "no-store" }
  )
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}
