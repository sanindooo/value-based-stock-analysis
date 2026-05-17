import { NextRequest, NextResponse } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export const dynamic = "force-dynamic"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  const { searchParams } = new URL(request.url)
  const type = searchParams.get("type")

  if (type === "status") {
    const res = await backendFetch(`/api/research/status/${id}`, {
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
    })
    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  }

  const res = await backendFetch(`/api/research/${id}`, {
    headers: { "Content-Type": "application/json" },
  })
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}
