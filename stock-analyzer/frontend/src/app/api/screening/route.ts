import { NextRequest, NextResponse } from "next/server"
import { revalidateTag } from "next/cache"
import { backendFetch } from "@/lib/backend-fetch"

export async function GET() {
  const res = await backendFetch("/api/screening/runs", {
    cache: "force-cache",
    next: { tags: ["screening-runs"], revalidate: 300 },
    headers: { "Content-Type": "application/json" },
  })
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}

export async function POST(request: NextRequest) {
  const body = await request.json()
  const res = await backendFetch("/api/screening/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  const data = await res.json()
  if (res.ok) revalidateTag("screening-runs", "max")
  return NextResponse.json(data, { status: res.status })
}
