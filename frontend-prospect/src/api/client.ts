/**
 * Minimal fetch helpers for the prospect app.
 *
 * The prospect only needs three endpoints: start a chat session, stream a
 * turn, and (optionally) fetch persisted messages for session rehydration.
 * We hand-roll the small amount of typing we need rather than pulling in
 * openapi-fetch, which would carry the full broker API surface.
 */

const BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export type MessageRole = 'USER' | 'ASSISTANT' | 'SYSTEM'

export interface ChatMessageOut {
  id: string
  lead_id: string
  role: MessageRole
  content: string
  created_at: string
}

export interface ChatSessionOut {
  lead_id: string
  greeting: string
}

export type DocumentStatus = 'UPLOADED' | 'PROCESSING' | 'EXTRACTED' | 'FAILED'

export interface DocumentExtractionOut {
  policy_type: string | null
  provider: string | null
  sum_insured: string | number | null
  premium_amount: string | number | null
  premium_frequency: string | null
  renewal_date: string | null
}

export interface DocumentOut {
  id: string
  lead_id: string
  original_filename: string
  mime_type: string
  size_bytes: number
  page_count: number | null
  status: DocumentStatus
  error_message: string | null
  created_at: string
  updated_at: string
  extraction: DocumentExtractionOut | null
}

export interface LeadDetailOut {
  id: string
  full_name: string | null
  email: string | null
  phone: string | null
  city: string | null
  status: string
  qualification_score: number
  extracted_fields: Record<string, unknown>
  messages: ChatMessageOut[]
  documents: DocumentOut[]
}

export interface DocumentUploadResponse {
  document_id: string
  status: DocumentStatus
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`HTTP ${res.status}: ${text.slice(0, 200)}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  async createSession(source: 'WEB' = 'WEB'): Promise<ChatSessionOut> {
    const res = await fetch(`${BASE}/api/chat/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source }),
    })
    return json<ChatSessionOut>(res)
  },

  async getLead(leadId: string): Promise<LeadDetailOut> {
    const res = await fetch(`${BASE}/api/leads/${leadId}`, {
      headers: { Accept: 'application/json' },
    })
    return json<LeadDetailOut>(res)
  },

  async deleteDocument(documentId: string): Promise<void> {
    const res = await fetch(`${BASE}/api/documents/${documentId}`, {
      method: 'DELETE',
    })
    if (!res.ok && res.status !== 204) {
      let detail = ''
      try {
        const body = (await res.json()) as { detail?: string }
        detail = body?.detail ?? ''
      } catch {
        // swallow
      }
      throw new Error(detail || `Delete failed (${res.status})`)
    }
  },

  async uploadDocument(leadId: string, file: File): Promise<DocumentUploadResponse> {
    const fd = new FormData()
    fd.append('lead_id', leadId)
    fd.append('file', file)
    const res = await fetch(`${BASE}/api/documents`, {
      method: 'POST',
      body: fd,
    })
    if (!res.ok) {
      let detail = ''
      try {
        const body = (await res.json()) as { detail?: string }
        detail = body?.detail ?? ''
      } catch {
        // swallow — we'll fall through to a generic message
      }
      throw new Error(detail || `Upload failed (${res.status})`)
    }
    return (await res.json()) as DocumentUploadResponse
  },
}
