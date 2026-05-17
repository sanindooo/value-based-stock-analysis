import { NextResponse } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function GET() {
  const res = await backendFetch("/api/screening/thresholds", {
    cache: "force-cache",
    next: { tags: ["preferences"], revalidate: 3600 },
    headers: { "Content-Type": "application/json" },
  })
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}
