import { NextRequest, NextResponse } from "next/server"
import { revalidateTag } from "next/cache"
import { backendFetch } from "@/lib/backend-fetch"

export async function POST(
  _request: NextRequest,
  { params }: { params: Promise<{ taskId: string }> }
) {
  const { taskId } = await params
  const res = await backendFetch(`/api/screening/tasks/${taskId}/cancel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  })
  const data = await res.json()
  if (res.ok) revalidateTag("screening-runs", "max")
  return NextResponse.json(data, { status: res.status })
}
