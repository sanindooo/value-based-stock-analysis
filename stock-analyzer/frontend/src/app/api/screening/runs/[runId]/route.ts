import { NextRequest, NextResponse } from "next/server"
import { revalidateTag } from "next/cache"
import { backendFetch } from "@/lib/backend-fetch"

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ runId: string }> }
) {
  const { runId } = await params
  const res = await backendFetch(`/api/screening/runs/${runId}`, {
    cache: "force-cache",
    next: { tags: [`screening-run-${runId}`, "screening-runs"], revalidate: 3600 },
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
  if (res.ok) {
    revalidateTag("screening-runs", "max")
    revalidateTag("screening-highlights", "max")
  }
  if (res.status === 204) {
    return new NextResponse(null, { status: 204 })
  }
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}
