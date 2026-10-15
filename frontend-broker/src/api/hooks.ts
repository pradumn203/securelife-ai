/**
 * Broker-side react-query hooks.
 *
 * Prospect-side chat hooks live in the sibling `frontend-prospect` app.
 * Everything here is CRM-flavored: list, detail, edit, delete, documents,
 * analysis. All queryKeys are stable arrays.
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from '@tanstack/react-query'
import { api } from '@/api/client'
import type { components } from '@/api/types'

type LeadDetailOut = components['schemas']['LeadDetailOut']
type LeadOut = components['schemas']['LeadOut']
type LeadStatus = components['schemas']['LeadStatus']
type LeadUpdate = components['schemas']['LeadUpdate']
type DocumentOut = components['schemas']['DocumentOut']
type DocumentUploadResponse = components['schemas']['DocumentUploadResponse']
type AnalysisOut = components['schemas']['AnalysisOut']
type QualificationOut = components['schemas']['QualificationOut']

/** Query key for a single lead detail payload. */
export const leadDetailKey = (leadId: string) => ['lead', leadId] as const

/**
 * Hydrate a lead's detail payload (messages + documents + latest_analysis).
 */
export function useLeadDetail(leadId: string | null) {
  return useQuery<LeadDetailOut>({
    queryKey: leadDetailKey(leadId ?? ''),
    enabled: Boolean(leadId),
    queryFn: async () => {
      if (!leadId) throw new Error('leadId is required')
      const { data, error } = await api.GET('/api/leads/{lead_id}', {
        params: { path: { lead_id: leadId } },
      })
      if (error) throw new Error(JSON.stringify(error))
      if (!data) throw new Error(`Lead ${leadId} not found`)
      return data
    },
    staleTime: 2_000,
  })
}

// ────────────────────────────────────────────────────────────────────────────
// Dashboard / prospect-list hooks.
// ────────────────────────────────────────────────────────────────────────────

export interface UseLeadsParams {
  status?: LeadStatus | null
  search?: string | null
  limit?: number
}

/** Stable query-key for the pipeline list, parameterised by filters. */
export const leadsListKey = (params: UseLeadsParams) =>
  [
    'leads',
    {
      status: params.status ?? null,
      search: params.search ?? '',
      limit: params.limit ?? null,
    },
  ] as const

/**
 * Pipeline list hook. Polls every 5s so new leads created mid-chat appear
 * without a manual refresh. Previous results are kept during refetch so the
 * grid doesn't flash to empty.
 */
export function useLeads(params: UseLeadsParams = {}) {
  const { status, search, limit } = params
  return useQuery<LeadOut[]>({
    queryKey: leadsListKey(params),
    queryFn: async () => {
      const { data, error } = await api.GET('/api/leads', {
        params: {
          query: {
            status: status ?? null,
            search: search && search.length > 0 ? search : null,
            ...(limit !== undefined ? { limit } : {}),
          },
        },
      })
      if (error) throw new Error(JSON.stringify(error))
      return data ?? []
    },
    refetchInterval: 5_000,
    placeholderData: (previous) => previous,
  })
}

/**
 * "Run qualification agent". Resolves with the finalised qualification
 * (verdict, score, evidence-backed dimensions); the lead's status moves to
 * QUALIFIED / DISQUALIFIED, or stays NEW on NEEDS_MORE_INFO.
 *
 * The server returns 400 — without calling the agent — when core facts are
 * not yet captured; the detail body carries a `missing` list of labels.
 */
export function useQualifyLead() {
  const qc = useQueryClient()
  return useMutation<QualificationOut, Error & { missing?: string[] }, string>({
    mutationFn: async (leadId: string) => {
      const { data, error } = await api.POST('/api/leads/{lead_id}/qualify', {
        params: { path: { lead_id: leadId } },
      })
      if (error) {
        // FastAPI puts our detail dict under `detail` on 4xx responses.
        const detail = (error as { detail?: unknown }).detail
        if (detail && typeof detail === 'object') {
          const d = detail as { message?: string; missing?: string[] }
          const err = new Error(d.message ?? 'Qualification failed') as Error & {
            missing?: string[]
          }
          err.missing = d.missing ?? []
          throw err
        }
        throw new Error(typeof detail === 'string' ? detail : 'Qualification failed')
      }
      if (!data) throw new Error('Qualify returned no body')
      return data
    },
    onSuccess: (_qualification, leadId) => {
      void qc.invalidateQueries({ queryKey: leadDetailKey(leadId) })
      void qc.invalidateQueries({ queryKey: ['leads'] })
    },
  })
}

/**
 * Delete a lead and all its children (messages, documents, extractions,
 * analyses). The server cascades via ORM `all, delete-orphan`.
 */
export function useDeleteLead() {
  const qc = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: async (leadId: string) => {
      const { error } = await api.DELETE('/api/leads/{lead_id}', {
        params: { path: { lead_id: leadId } },
      })
      if (error) throw new Error(JSON.stringify(error))
    },
    onSuccess: (_void, leadId) => {
      void qc.invalidateQueries({ queryKey: ['leads'] })
      qc.removeQueries({ queryKey: leadDetailKey(leadId) })
    },
  })
}

/**
 * Broker-side edit mutation. Invalidates both the lead detail and the pipeline
 * list on success so the dialog closes against fresh data.
 */
export function usePatchLead(leadId: string | undefined) {
  const qc = useQueryClient()
  return useMutation<LeadOut, Error, LeadUpdate>({
    mutationFn: async (payload) => {
      if (!leadId) throw new Error('leadId is required')
      const { data, error } = await api.PATCH('/api/leads/{lead_id}', {
        params: { path: { lead_id: leadId } },
        body: payload,
      })
      if (error) {
        const detail = (error as { detail?: unknown }).detail
        throw new Error(typeof detail === 'string' ? detail : 'Could not save the changes.')
      }
      if (!data) throw new Error('PATCH returned no body')
      return data
    },
    onSuccess: () => {
      if (leadId) qc.invalidateQueries({ queryKey: leadDetailKey(leadId) })
      qc.invalidateQueries({ queryKey: ['leads'] })
    },
  })
}

// ────────────────────────────────────────────────────────────────────────────
// Documents + analysis hooks.
// ────────────────────────────────────────────────────────────────────────────

/** Stable query key for a lead's document list. */
export const leadDocumentsKey = (leadId: string) =>
  ['documents', 'by-lead', leadId] as const

/** Stable query key for a single document resource (used for polling). */
export const documentKey = (documentId: string) =>
  ['document', documentId] as const

/** Stable query key for a lead's latest analysis. */
export const latestAnalysisKey = (leadId: string) =>
  ['analysis', 'latest', leadId] as const

/** Fetch the list of documents attached to a lead. */
export function useLeadDocuments(
  leadId: string | undefined,
  options?: Partial<UseQueryOptions<DocumentOut[]>>
) {
  return useQuery<DocumentOut[]>({
    queryKey: leadDocumentsKey(leadId ?? ''),
    queryFn: async () => {
      const { data, error } = await api.GET('/api/documents', {
        params: { query: { lead_id: leadId as string } },
      })
      if (error) throw new Error(JSON.stringify(error))
      return (data ?? []) as DocumentOut[]
    },
    enabled: Boolean(leadId),
    ...options,
  })
}

/**
 * Broker-triggered run of the document extractor agent. Called from the
 * DocumentCard's "Run extractor agent" and "Retry" buttons; the backend flips
 * UPLOADED / FAILED documents to PROCESSING and starts the background task.
 */
export function useExtractDocument() {
  const qc = useQueryClient()
  return useMutation<DocumentOut, Error, { documentId: string; leadId: string }>({
    mutationFn: async ({ documentId }) => {
      const { data, error } = await api.POST('/api/documents/{document_id}/extract', {
        params: { path: { document_id: documentId } },
      })
      if (error) throw new Error(JSON.stringify(error))
      if (!data) throw new Error('Extract returned no body')
      return data as DocumentOut
    },
    onSuccess: (doc, { documentId, leadId }) => {
      // Seed the per-document cache with the PROCESSING row so the card's
      // status poll starts immediately instead of reading a stale terminal state.
      qc.setQueryData(documentKey(documentId), doc)
      void qc.invalidateQueries({ queryKey: leadDocumentsKey(leadId) })
      void qc.invalidateQueries({ queryKey: leadDetailKey(leadId) })
    },
  })
}

/**
 * Multipart document upload. Hand-crafted because `openapi-fetch` doesn't
 * ergonomically handle multipart bodies — the backend expects
 * `multipart/form-data` with `lead_id` + `file` parts.
 *
 * On success, the lead's document list is invalidated so the fresh card
 * appears without a manual refresh.
 */
export function useUploadDocument(leadId: string) {
  const qc = useQueryClient()
  return useMutation<DocumentUploadResponse, Error, File>({
    mutationFn: async (file: File) => {
      const fd = new FormData()
      fd.append('lead_id', leadId)
      fd.append('file', file)
      const base = (import.meta.env.VITE_API_BASE_URL ?? '') as string
      const res = await fetch(`${base}/api/documents`, {
        method: 'POST',
        body: fd,
      })
      if (!res.ok) {
        let detail = ''
        try {
          const body = (await res.json()) as { detail?: string }
          detail = body?.detail ?? ''
        } catch {
          // ignore JSON parse errors
        }
        throw new Error(detail || `Upload failed (${res.status})`)
      }
      return (await res.json()) as DocumentUploadResponse
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: leadDocumentsKey(leadId) })
      void qc.invalidateQueries({ queryKey: leadDetailKey(leadId) })
    },
  })
}

/**
 * Poll a single document until its status reaches a terminal state
 * (EXTRACTED or FAILED). Pass `enabled: false` to skip polling.
 *
 * Polling cadence is 1.5s — fast enough to feel live, slow enough to not
 * hammer the backend while an extraction (5–15s) runs.
 */
export function useDocumentStatus(
  documentId: string | undefined,
  options?: { enabled?: boolean }
) {
  const enabled = Boolean(documentId) && (options?.enabled ?? true)
  const qc = useQueryClient()
  return useQuery<DocumentOut>({
    queryKey: documentKey(documentId ?? ''),
    queryFn: async () => {
      const { data, error } = await api.GET('/api/documents/{document_id}', {
        params: { path: { document_id: documentId as string } },
      })
      if (error || !data) throw new Error(JSON.stringify(error ?? 'not found'))
      const doc = data as DocumentOut
      // When a doc transitions to a terminal state, we need to invalidate
      // BOTH the documents list (for the embedded extraction payload) AND
      // the lead detail (so `canGenerate` on LeadDetailPage picks up that
      // an EXTRACTED document now exists on this lead).
      if (doc.status === 'EXTRACTED' || doc.status === 'FAILED') {
        void qc.invalidateQueries({ queryKey: leadDocumentsKey(doc.lead_id) })
        void qc.invalidateQueries({ queryKey: leadDetailKey(doc.lead_id) })
      }
      return doc
    },
    enabled,
    refetchInterval: (query) => {
      const doc = query.state.data as DocumentOut | undefined
      if (!doc) return 1500
      // Only poll while actively processing. UPLOADED is a waiting state —
      // extraction doesn't start until the broker runs the extractor agent.
      return doc.status === 'PROCESSING' ? 1500 : false
    },
    refetchIntervalInBackground: false,
  })
}

/**
 * Delete a document (and its extraction) by id. On success, invalidate the
 * lead's document list AND lead detail so the UI picks up the removal and
 * `canGenerate` recalculates.
 */
export function useDeleteDocument() {
  const qc = useQueryClient()
  return useMutation<void, Error, { documentId: string; leadId: string }>({
    mutationFn: async ({ documentId }) => {
      const { error } = await api.DELETE('/api/documents/{document_id}', {
        params: { path: { document_id: documentId } },
      })
      if (error) throw new Error(JSON.stringify(error))
    },
    onSuccess: (_v, { documentId, leadId }) => {
      qc.removeQueries({ queryKey: documentKey(documentId) })
      void qc.invalidateQueries({ queryKey: leadDocumentsKey(leadId) })
      void qc.invalidateQueries({ queryKey: leadDetailKey(leadId) })
    },
  })
}

/** Fetch the latest analysis for a lead (may be null). */
export function useLatestAnalysis(leadId: string | undefined) {
  return useQuery<AnalysisOut | null>({
    queryKey: latestAnalysisKey(leadId ?? ''),
    queryFn: async () => {
      const { data, error } = await api.GET('/api/analysis', {
        params: { query: { lead_id: leadId as string } },
      })
      if (error) throw new Error(JSON.stringify(error))
      return (data ?? null) as AnalysisOut | null
    },
    enabled: Boolean(leadId),
  })
}

/**
 * Run the analysis agent for the given lead. The backend endpoint is
 * synchronous, so the mutation resolves with the full `AnalysisOut` payload.
 */
export function useGenerateAnalysis(leadId: string) {
  const qc = useQueryClient()
  return useMutation<AnalysisOut, Error, void>({
    mutationFn: async () => {
      const { data, error } = await api.POST('/api/analysis/generate', {
        body: { lead_id: leadId },
      })
      if (error || !data) {
        const detail = (error as { detail?: unknown } | undefined)?.detail
        throw new Error(typeof detail === 'string' ? detail : 'The analysis agent could not run. Please try again.')
      }
      return data as AnalysisOut
    },
    onSuccess: (fresh) => {
      qc.setQueryData<AnalysisOut | null>(latestAnalysisKey(leadId), fresh)
      void qc.invalidateQueries({ queryKey: leadDetailKey(leadId) })
    },
  })
}
