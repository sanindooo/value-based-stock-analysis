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
  // Always invalidate reports cache during active research polling —
  // background tasks complete and create reports without going through
  // the Next.js cache layer, so the cached report list goes stale.
  if (res.ok) {
    revalidateTag("research-reports", "max")
  }
  return NextResponse.json(data, { status: res.status })
}
