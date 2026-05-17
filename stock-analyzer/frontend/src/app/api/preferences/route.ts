import { NextRequest, NextResponse } from "next/server"
import { revalidateTag } from "next/cache"
import { backendFetch } from "@/lib/backend-fetch"

export async function GET() {
  const res = await backendFetch("/api/preferences", {
    cache: "force-cache",
    next: { tags: ["preferences"], revalidate: 3600 },
    headers: { "Content-Type": "application/json" },
  })
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}

export async function PUT(request: NextRequest) {
  const body = await request.json()
  const res = await backendFetch("/api/preferences", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  const data = await res.json()
  if (res.ok) revalidateTag("preferences", "max")
  return NextResponse.json(data, { status: res.status })
}
