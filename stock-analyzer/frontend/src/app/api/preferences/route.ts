import { NextRequest, NextResponse } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export const dynamic = "force-dynamic"

export async function GET() {
  const res = await backendFetch("/api/preferences", {
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
  return NextResponse.json(data, { status: res.status })
}
