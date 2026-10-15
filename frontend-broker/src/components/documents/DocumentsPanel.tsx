import * as React from 'react'
import { FileText } from 'lucide-react'
import type { components } from '@/api/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useLeadDocuments, useUploadDocument } from '@/api/hooks'
import { DocumentCard } from './DocumentCard'
import { DocumentUpload } from './DocumentUpload'

type DocumentOut = components['schemas']['DocumentOut']

export interface DocumentsPanelProps {
  leadId: string
  /**
   * Documents already loaded by the parent (`LeadDetailOut.documents`).
   * We use them as the initial render but refresh in the background to pick
   * up newly-finished extractions.
   */
  documents: DocumentOut[]
}

/**
 * Documents panel embedded in LeadDetailPage. Self-fetches to stay in sync
 * with the backend; the parent doesn't need to re-fetch on our behalf.
 */
export function DocumentsPanel({ leadId, documents }: DocumentsPanelProps) {
  const docsQuery = useLeadDocuments(leadId, {
    initialData: documents,
  })
  const upload = useUploadDocument(leadId)
  // Documents whose server resource we haven't seen yet, keyed by a local id.
  // We display them until the real id appears in `docsQuery.data`.
  const [optimistic, setOptimistic] = React.useState<DocumentOut[]>([])

  const serverDocs = docsQuery.data ?? documents

  // Prune optimistic entries once the server has acknowledged a matching id.
  React.useEffect(() => {
    if (optimistic.length === 0) return
    const serverIds = new Set(serverDocs.map((d) => d.id))
    setOptimistic((prev) => prev.filter((o) => !serverIds.has(o.id)))
    // We intentionally depend only on `serverDocs` — mutating `optimistic`
    // inside the setter is safe.
  }, [serverDocs, optimistic.length])

  const handleUpload = React.useCallback(
    async (file: File) => {
      const localId = `optimistic-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
      const placeholder: DocumentOut = {
        id: localId,
        lead_id: leadId,
        original_filename: file.name,
        mime_type: file.type,
        size_bytes: file.size,
        page_count: null,
        status: 'UPLOADED',
        error_message: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }
      setOptimistic((prev) => [placeholder, ...prev])
      try {
        const resp = await upload.mutateAsync(file)
        // Swap the optimistic placeholder's id to the real one so the card
        // starts polling the actual document resource.
        setOptimistic((prev) =>
          prev.map((o) =>
            o.id === localId ? { ...o, id: resp.document_id, status: resp.status } : o
          )
        )
      } catch {
        setOptimistic((prev) => prev.filter((o) => o.id !== localId))
      }
    },
    [leadId, upload]
  )

  // Merge: optimistic entries first, then the server list minus duplicates.
  const serverIds = new Set(serverDocs.map((d) => d.id))
  const merged: DocumentOut[] = [
    ...optimistic.filter((o) => !serverIds.has(o.id)),
    ...serverDocs,
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-brand-600" aria-hidden="true" />
          Documents
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <DocumentUpload
          onUpload={handleUpload}
          isUploading={upload.isPending}
          errorMessage={upload.error?.message ?? null}
        />
        {merged.length === 0 ? (
          <p className="text-sm text-slate-500">
            No documents uploaded yet. Upload a policy PDF to start extraction.
          </p>
        ) : (
          <div className="space-y-3">
            {merged.map((doc) => (
              <DocumentCard
                key={doc.id}
                document={doc}
                isOptimistic={doc.id.startsWith('optimistic-')}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
