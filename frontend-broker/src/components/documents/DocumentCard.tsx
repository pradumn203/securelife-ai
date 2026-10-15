import * as React from 'react'
import { AlertTriangle, FileText, Loader2, Play, RefreshCw, Trash2 } from 'lucide-react'
import type { components } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogFooter } from '@/components/ui/dialog'
import { cn } from '@/lib/utils'
import { useDeleteDocument, useDocumentStatus, useExtractDocument } from '@/api/hooks'
import { ExtractionPanel } from './ExtractionPanel'

type DocumentOut = components['schemas']['DocumentOut']
type DocumentStatus = components['schemas']['DocumentStatus']

export interface DocumentCardProps {
  document: DocumentOut
  /**
   * When true, this card is a locally-created optimistic placeholder (an
   * upload we just kicked off). The real document resource arrives via the
   * polling hook once the backend acknowledges the upload.
   */
  isOptimistic?: boolean
}

const STATUS_LABEL: Record<DocumentStatus, string> = {
  UPLOADED: 'Awaiting extraction',
  PROCESSING: 'Agent extracting…',
  EXTRACTED: 'Extracted',
  FAILED: 'Failed',
}

const STATUS_VARIANT: Record<
  DocumentStatus,
  'secondary' | 'warning' | 'success' | 'danger'
> = {
  UPLOADED: 'secondary',
  PROCESSING: 'warning',
  EXTRACTED: 'success',
  FAILED: 'danger',
}

const formatSize = (bytes: number): string => {
  if (!Number.isFinite(bytes) || bytes <= 0) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function DocumentCard({ document, isOptimistic }: DocumentCardProps) {
  // Poll the backend for status until EXTRACTED/FAILED. Skip entirely when the
  // document is already terminal — avoids a wasted request on the first paint.
  const isTerminal =
    document.status === 'EXTRACTED' || document.status === 'FAILED'
  const polled = useDocumentStatus(document.id, {
    enabled: !isOptimistic && !isTerminal,
  })
  const current: DocumentOut = polled.data ?? document
  const status = current.status
  const extraction = current.extraction ?? null
  const isUploaded = status === 'UPLOADED'
  const isProcessing = status === 'PROCESSING'
  const isFailed = status === 'FAILED'
  const isExtracted = status === 'EXTRACTED'

  const [confirmDelete, setConfirmDelete] = React.useState(false)
  const del = useDeleteDocument()
  const extract = useExtractDocument()
  const onConfirmDelete = async () => {
    try {
      await del.mutateAsync({ documentId: current.id, leadId: current.lead_id })
      setConfirmDelete(false)
    } catch {
      // keep dialog open; error shown below
    }
  }
  const onRunExtractor = () => {
    extract.mutate({ documentId: current.id, leadId: current.lead_id })
  }

  return (
    <div
      className={cn(
        'rounded-xl border bg-white p-4 shadow-sm transition-colors',
        isFailed
          ? 'border-red-200 bg-red-50/30'
          : isExtracted
            ? 'border-emerald-200/70'
            : 'border-slate-200'
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <div
            className={cn(
              'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg',
              isFailed
                ? 'bg-red-100 text-red-600'
                : isExtracted
                  ? 'bg-emerald-100 text-emerald-700'
                  : 'bg-brand-100 text-brand-700'
            )}
          >
            <FileText className="h-5 w-5" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-slate-900">
              {current.original_filename}
            </p>
            <p className="text-xs text-slate-500">
              {formatSize(current.size_bytes)}
              {typeof current.page_count === 'number'
                ? ` · ${current.page_count} page${current.page_count === 1 ? '' : 's'}`
                : ''}
            </p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {isProcessing ? (
            <Loader2 className="h-4 w-4 animate-spin text-amber-600" aria-hidden="true" />
          ) : null}
          <Badge variant={STATUS_VARIANT[status]}>{STATUS_LABEL[status]}</Badge>
          {!isOptimistic && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-slate-400 hover:bg-red-50 hover:text-red-600"
              onClick={() => setConfirmDelete(true)}
              title="Delete this document"
              aria-label="Delete document"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </div>

      {isUploaded && !isOptimistic ? (
        <div className="mt-3 flex items-start justify-between gap-3 rounded-md border border-amber-200 bg-white p-3">
          <div className="flex min-w-0 items-start gap-2">
            <Play
              className="mt-0.5 h-4 w-4 shrink-0 text-amber-600"
              aria-hidden="true"
            />
            <div className="min-w-0">
              <p className="text-sm font-medium text-slate-900">
                Awaiting extraction
              </p>
              <p className="text-xs text-slate-500">
                Run the document extractor agent to pull out the structured
                policy data, with evidence for every field.
              </p>
            </div>
          </div>
          <Button
            type="button"
            variant="default"
            size="sm"
            onClick={onRunExtractor}
            disabled={extract.isPending}
          >
            {extract.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Play className="h-3.5 w-3.5" />
            )}
            {extract.isPending ? 'Starting agent…' : 'Run extractor agent'}
          </Button>
        </div>
      ) : null}

      {extract.error && (isUploaded || isFailed) ? (
        <p className="mt-2 rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">
          Could not start the extractor agent: {extract.error.message}
        </p>
      ) : null}

      {isFailed ? (
        <div className="mt-3 flex items-start justify-between gap-3 rounded-md border border-red-200 bg-white p-3">
          <div className="flex min-w-0 items-start gap-2">
            <AlertTriangle
              className="mt-0.5 h-4 w-4 shrink-0 text-red-600"
              aria-hidden="true"
            />
            <div className="min-w-0">
              <p className="text-sm font-medium text-red-900">
                Extraction failed
              </p>
              <p className="truncate text-xs text-red-700">
                {current.error_message ?? 'Unknown error.'}
              </p>
            </div>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onRunExtractor}
            disabled={extract.isPending}
            title="Re-run the document extractor agent on the stored PDF."
          >
            {extract.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
            )}
            Retry agent
          </Button>
        </div>
      ) : null}

      {isExtracted && extraction ? (
        <div className="mt-4 border-t border-slate-100 pt-4">
          <ExtractionPanel extraction={extraction} />
        </div>
      ) : null}

      <Dialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title="Delete this document?"
        description={
          `This permanently removes "${current.original_filename}" and its ` +
          `extracted data. The analysis card (if any) is kept. This cannot be undone.`
        }
      >
        {del.error && (
          <p className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">
            Could not delete: {del.error.message}
          </p>
        )}
        <DialogFooter>
          <Button type="button" variant="ghost" onClick={() => setConfirmDelete(false)}>
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={onConfirmDelete}
            disabled={del.isPending}
          >
            {del.isPending ? 'Deleting…' : 'Delete'}
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  )
}
