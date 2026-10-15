import * as React from 'react'
import { Check, FileText, Loader2, Trash2, UploadCloud, X } from 'lucide-react'
import { api, type DocumentOut, type DocumentStatus } from '@/api/client'
import { useInvalidateLeadDetail } from '@/api/hooks'
import { cn } from '@/lib/utils'

const MAX_SIZE_BYTES = 20 * 1024 * 1024
const POLL_MS = 2_000

interface DocumentShareProps {
  leadId: string | null
  documents: DocumentOut[]
}

/**
 * Compact prospect-facing upload affordance.
 *
 * Mirrors the broker's `DocumentUpload` but with less chrome: a drag-drop zone,
 * client-side PDF+size validation, and a short list of previously-shared files
 * with their processing state. All uploads hit the same backend endpoint, so
 * the broker's dashboard will show these documents on the same lead.
 */
export function DocumentShare({ leadId, documents }: DocumentShareProps) {
  const [uploading, setUploading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [dragOver, setDragOver] = React.useState(false)
  const [deletingId, setDeletingId] = React.useState<string | null>(null)
  const inputRef = React.useRef<HTMLInputElement | null>(null)
  const invalidate = useInvalidateLeadDetail()

  const handleDelete = async (docId: string, filename: string) => {
    if (!leadId) return
    const ok = window.confirm(`Remove "${filename}"? This cannot be undone.`)
    if (!ok) return
    setError(null)
    setDeletingId(docId)
    try {
      await api.deleteDocument(docId)
      invalidate(leadId)
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Delete failed.')
    } finally {
      setDeletingId(null)
    }
  }

  // Keep polling the lead detail while any document is actively processing.
  // UPLOADED documents are waiting on the broker to run the extractor agent — no
  // point polling since nothing will change until the broker acts.
  const inFlight = React.useMemo(
    () => documents.some((d) => d.status === 'PROCESSING'),
    [documents]
  )
  React.useEffect(() => {
    if (!leadId || !inFlight) return
    const id = window.setInterval(() => invalidate(leadId), POLL_MS)
    return () => window.clearInterval(id)
  }, [leadId, inFlight, invalidate])

  const handleFile = async (file: File) => {
    setError(null)
    if (!leadId) {
      setError('Hold on — your chat session is still starting up.')
      return
    }
    const looksLikePdf =
      file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
    if (!looksLikePdf) {
      setError('Only PDF files are accepted.')
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

  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file) void handleFile(file)
  }

  const onPick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) void handleFile(file)
    // Clear so the same file can be re-selected if needed.
    e.target.value = ''
  }

  return (
    <section className="mt-4 rounded-xl border border-slate-200/80 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">
            Share a policy document
          </h2>
          <p className="mt-0.5 text-xs text-slate-500">
            Optional — upload an existing policy and the broker will review it
            before reaching out.
          </p>
        </div>
      </div>

      <div
        onDrop={onDrop}
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            inputRef.current?.click()
          }
        }}
        className={cn(
          'mt-3 flex cursor-pointer flex-col items-center justify-center gap-1.5 rounded-lg border-2 border-dashed p-5 text-center text-xs transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500',
          dragOver
            ? 'border-brand-500 bg-brand-50'
            : 'border-slate-300 hover:border-slate-400 hover:bg-slate-50',
          uploading && 'pointer-events-none opacity-70'
        )}
      >
        <UploadCloud className="h-5 w-5 text-slate-400" />
        <div className="font-medium text-slate-700">
          {uploading ? 'Uploading…' : 'Drag a PDF here or click to choose'}
        </div>
        <div className="text-[11px] text-slate-400">PDF only · max 20 MB</div>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf"
          className="hidden"
          onChange={onPick}
        />
      </div>

      {error && (
        <p className="mt-2 rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">
          {error}
        </p>
      )}

      {documents.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {documents.map((doc) => (
            <li
              key={doc.id}
              className="flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50/60 px-3 py-2 text-xs"
            >
              <FileText className="h-3.5 w-3.5 shrink-0 text-slate-500" />
              <span className="flex-1 truncate text-slate-700" title={doc.original_filename}>
                {doc.original_filename}
              </span>
              <StatusPill status={doc.status} />
              <button
                type="button"
                onClick={() => void handleDelete(doc.id, doc.original_filename)}
                disabled={deletingId === doc.id}
                aria-label={`Remove ${doc.original_filename}`}
                title="Remove this document"
                className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {deletingId === doc.id ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Trash2 className="h-3.5 w-3.5" />
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function StatusPill({ status }: { status: DocumentStatus }) {
  if (status === 'UPLOADED') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-700">
        Shared · awaiting review
      </span>
    )
  }
  if (status === 'PROCESSING') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-800">
        <Loader2 className="h-3 w-3 animate-spin" />
        Analyzing
      </span>
    )
  }
  if (status === 'EXTRACTED') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-medium text-emerald-800">
        <Check className="h-3 w-3" />
        Ready
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-medium text-red-800">
      <X className="h-3 w-3" />
      Could not read
    </span>
  )
}
