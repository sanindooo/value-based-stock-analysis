import { NextRequest, NextResponse } from "next/server"
import { revalidateTag } from "next/cache"
import { backendFetch } from "@/lib/backend-fetch"

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
  if (res.ok) {
    revalidateTag(`screening-run-${runId}`, "max")
    revalidateTag("screening-runs", "max")
    revalidateTag("screening-highlights", "max")
  }
  return NextResponse.json(data, { status: res.status })
}
