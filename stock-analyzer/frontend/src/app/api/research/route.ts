import { NextRequest, NextResponse } from "next/server"
import { revalidateTag } from "next/cache"
import { backendFetch } from "@/lib/backend-fetch"

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const qs = searchParams.toString()
  const path = `/api/research/reports${qs ? `?${qs}` : ""}`
  const res = await backendFetch(path, {
    cache: "force-cache",
    next: { tags: ["research-reports"], revalidate: 300 },
    headers: { "Content-Type": "application/json" },
  })
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}

export async function POST(request: NextRequest) {
  const body = await request.json()
  const res = await backendFetch("/api/research/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  const data = await res.json()
  if (res.ok) revalidateTag("research-reports", "max")
  return NextResponse.json(data, { status: res.status })
}
