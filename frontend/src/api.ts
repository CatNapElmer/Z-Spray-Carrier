import { apiUrl } from './config'

export async function apiFetch(path: string, init?: RequestInit, timeoutMs = 90_000): Promise<Response> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    return await fetch(apiUrl(path), { ...init, signal: controller.signal })
  } finally {
    window.clearTimeout(timer)
  }
}
