import createClient from 'openapi-fetch'
import type { paths } from './types'

/**
 * Typed API client. All requests are relative; Vite proxies /api → :8000 in dev.
 * In production, set VITE_API_BASE_URL to the backend origin.
 */
export const api = createClient<paths>({
  baseUrl: import.meta.env.VITE_API_BASE_URL ?? '',
})
