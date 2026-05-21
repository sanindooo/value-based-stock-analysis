import { NextRequest, NextResponse } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function POST(request: NextRequest) {
  const url = new URL(request.url)
  const ticker = url.searchParams.get("ticker")
  const tier = url.searchParams.get("tier") || "standard"

  if (!ticker) {
    return NextResponse.json({ error: "ticker required" }, { status: 400 })
  }

  const body = await request.json()
  const res = await backendFetch(`/api/analysis/${tier}/${ticker}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}
