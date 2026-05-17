import { NextRequest, NextResponse } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const qs = searchParams.toString()
  const path = `/api/screening/highlights${qs ? `?${qs}` : ""}`
  const res = await backendFetch(path, {
    cache: "force-cache",
    next: { tags: ["screening-highlights"], revalidate: 300 },
    headers: { "Content-Type": "application/json" },
  })
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}
