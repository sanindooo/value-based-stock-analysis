import { NextResponse } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export const dynamic = "force-dynamic"

export async function GET() {
  const res = await backendFetch("/api/research/active", {
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  })
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}
