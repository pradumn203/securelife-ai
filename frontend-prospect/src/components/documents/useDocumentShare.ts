import * as React from 'react'
import { api, type DocumentOut } from '@/api/client'
import { useInvalidateLeadDetail } from '@/api/hooks'

const MAX_SIZE_BYTES = 20 * 1024 * 1024
const POLL_MS = 2_000

/**
 * Upload / remove logic for the prospect's policy documents. The composer
 * renders the attach button and the file chips; this hook owns validation,
 * the API calls and polling. Uploads hit the same endpoint the broker uses,
 * so the documents land on the same lead.
 */
export function useDocumentShare(leadId: string | null, documents: DocumentOut[]) {
  const [uploading, setUploading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [deletingId, setDeletingId] = React.useState<string | null>(null)
  const invalidate = useInvalidateLeadDetail()

  // Poll while any document is being read. UPLOADED documents wait for the
  // broker, so nothing changes for them until the broker acts.
  const inFlight = documents.some((d) => d.status === 'PROCESSING')
  React.useEffect(() => {
    if (!leadId || !inFlight) return
    const id = window.setInterval(() => invalidate(leadId), POLL_MS)
    return () => window.clearInterval(id)
  }, [leadId, inFlight, invalidate])

  const upload = async (file: File) => {
    setError(null)
    if (!leadId) {
      setError('Hold on, your chat is still starting up.')
      return
    }
    const looksLikePdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
    if (!looksLikePdf) {
      setError('Only PDF files can be shared.')
      return
    }
    if (file.size > MAX_SIZE_BYTES) {
      setError('That file is too large. The limit is 20 MB.')
      return
    }
    setUploading(true)
    try {
      await api.uploadDocument(leadId, file)
      invalidate(leadId)
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Upload failed.')
    } finally {
      setUploading(false)
    }
  }

  const remove = async (doc: DocumentOut) => {
    if (!leadId) return
    if (!window.confirm(`Remove "${doc.original_filename}"? This cannot be undone.`)) return
    setError(null)
    setDeletingId(doc.id)
    try {
      await api.deleteDocument(doc.id)
      invalidate(leadId)
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Could not remove the file.')
    } finally {
      setDeletingId(null)
    }
  }

  const onPick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) void upload(file)
    e.target.value = '' // so the same file can be picked again
  }

  return {
    uploading,
    error,
    deletingId,
    onPick,
    upload,
    remove,
    clearError: () => setError(null),
  }
}

export type DocumentShareState = ReturnType<typeof useDocumentShare>
