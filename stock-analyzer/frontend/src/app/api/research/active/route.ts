import { NextResponse } from "next/server"
import { revalidateTag } from "next/cache"
import { backendFetch } from "@/lib/backend-fetch"

export const dynamic = "force-dynamic"

export async function GET() {
  const res = await backendFetch("/api/research/active", {
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
  })
  const data = await res.json()
  // When no active tasks remain, bust reports cache so completed ones appear
  if (res.ok && Array.isArray(data) && data.length === 0) {
    revalidateTag("research-reports", "max")
  }
  return NextResponse.json(data, { status: res.status })
}
