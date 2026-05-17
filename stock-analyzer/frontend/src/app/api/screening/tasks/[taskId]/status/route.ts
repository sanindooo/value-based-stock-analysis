import { NextRequest, NextResponse } from "next/server"
import { revalidateTag } from "next/cache"
import { backendFetch } from "@/lib/backend-fetch"

export const dynamic = "force-dynamic"

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ taskId: string }> }
) {
  const { taskId } = await params
  const res = await backendFetch(`/api/screening/tasks/${taskId}/status`, {
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
  })
  const data = await res.json()
  // When a task completes, bust the screening caches
  if (res.ok && data.status === "completed") {
    revalidateTag("screening-runs", "max")
    revalidateTag("screening-highlights", "max")
  }
  return NextResponse.json(data, { status: res.status })
}
