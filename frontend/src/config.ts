const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim()

export const API_BASE_URL = (configuredBaseUrl || 'http://localhost:8000').replace(/\/$/, '')

export function apiUrl(path: string): string {
  return `${API_BASE_URL}/api/${path.replace(/^\//, '')}`
}
