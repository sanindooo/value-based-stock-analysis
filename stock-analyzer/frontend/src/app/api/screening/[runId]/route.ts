import { NextRequest, NextResponse } from "next/server"
import { revalidateTag } from "next/cache"
import { backendFetch } from "@/lib/backend-fetch"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ runId: string }> }
) {
  const { runId } = await params
  const { searchParams } = new URL(request.url)
  const poll = searchParams.get("poll")

  const backendParams = new URLSearchParams(searchParams)
  backendParams.delete("poll")
  const qs = backendParams.toString()
  const path = `/api/screening/${runId}/results${qs ? `?${qs}` : ""}`

  const fetchOptions: RequestInit = poll
    ? { cache: "no-store", headers: { "Content-Type": "application/json" } }
    : { cache: "force-cache", next: { tags: [`screening-run-${runId}`], revalidate: 3600 }, headers: { "Content-Type": "application/json" } }

  const res = await backendFetch(path, fetchOptions)
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

  const res = await backendFetch(
    `/api/screening/${runId}/results/${resultId}/stage`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stage }),
    }
  )
  const data = await res.json()
  if (res.ok) {
    revalidateTag(`screening-run-${runId}`, "max")
    revalidateTag("screening-highlights", "max")
  }
  return NextResponse.json(data, { status: res.status })
}
