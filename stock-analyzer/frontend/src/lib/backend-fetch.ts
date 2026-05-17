const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

const RETRYABLE_CODES = new Set(["ETIMEDOUT", "ECONNREFUSED", "ECONNRESET", "UND_ERR_CONNECT_TIMEOUT"])
const MAX_RETRIES = 4
const BASE_DELAY_MS = 1000

function isRetryable(error: unknown): boolean {
  if (error instanceof TypeError && error.message === "fetch failed" && error.cause) {
    const cause = error.cause as { code?: string }
    return cause.code != null && RETRYABLE_CODES.has(cause.code)
  }
  return false
}

export async function backendFetch(path: string, init?: RequestInit): Promise<Response> {
  const url = `${BACKEND_URL}${path}`
  let lastError: unknown

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      return await fetch(url, init)
    } catch (error) {
      lastError = error
      if (attempt < MAX_RETRIES && isRetryable(error)) {
        await new Promise((r) => setTimeout(r, BASE_DELAY_MS * 2 ** attempt))
        continue
      }
      throw error
    }
  }

  throw lastError
}
