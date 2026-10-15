import { useRef, type ReactNode } from 'react'
import { Check, FileText, Loader2, Paperclip, X } from 'lucide-react'
import type { DocumentOut, DocumentStatus } from '@/api/client'
import { cn } from '@/lib/utils'
import type { DocumentShareState } from './useDocumentShare'

/** Paperclip button for the composer, plus the hidden file input it opens. */
export function AttachButton({ share, highlight }: { share: DocumentShareState; highlight?: boolean }) {
  const inputRef = useRef<HTMLInputElement>(null)
  return (
    <>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={share.uploading}
        title="Share a policy PDF (max 20 MB)"
        className={cn(
          'inline-flex h-9 items-center gap-2 rounded-full px-3 text-sm font-semibold transition-colors disabled:opacity-60',
          highlight ? 'bg-lime text-ink hover:bg-lime-strong' : 'text-muted hover:bg-mist hover:text-ink'
        )}
      >
        {share.uploading ? (
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        ) : (
          <Paperclip className="h-4 w-4" aria-hidden="true" />
        )}
        <span>{share.uploading ? 'Uploading…' : 'Attach policy'}</span>
      </button>
      <input ref={inputRef} type="file" accept="application/pdf" className="hidden" onChange={share.onPick} />
    </>
  )
}

/** Shared files as chips above the text box, like attachments in ChatGPT. */
export function DocumentChips({ share, documents }: { share: DocumentShareState; documents: DocumentOut[] }) {
  if (documents.length === 0 && !share.error) return null
  return (
    <div className="flex flex-wrap gap-2 px-2 pb-1 pt-1">
      {documents.map((doc) => (
        <div
          key={doc.id}
          className="flex max-w-full items-center gap-2.5 rounded-2xl border border-line bg-page py-1.5 pl-2 pr-1.5"
        >
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-ink">
            <FileText className="h-4 w-4 text-lime" aria-hidden="true" />
          </span>
          <span className="min-w-0">
            <span className="block max-w-[200px] truncate text-xs font-semibold text-ink" title={doc.original_filename}>
              {doc.original_filename}
            </span>
            <StatusLine status={doc.status} />
          </span>
          <button
            type="button"
            onClick={() => void share.remove(doc)}
            disabled={share.deletingId === doc.id}
            aria-label={`Remove ${doc.original_filename}`}
            className="rounded-full p-1 text-muted hover:bg-mist hover:text-ink disabled:opacity-50"
          >
            {share.deletingId === doc.id ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <X className="h-3.5 w-3.5" />
            )}
          </button>
        </div>
      ))}
      {share.error ? (
        <p className="flex w-full items-center justify-between gap-2 rounded-xl bg-red-50 px-3 py-2 text-xs font-medium text-red-700">
          {share.error}
          <button type="button" onClick={share.clearError} aria-label="Dismiss" className="rounded-full p-0.5 hover:bg-red-100">
            <X className="h-3.5 w-3.5" />
          </button>
        </p>
      ) : null}
    </div>
  )
}

function StatusLine({ status }: { status: DocumentStatus }) {
  const meta: Record<DocumentStatus, { text: string; className: string; icon?: ReactNode }> = {
    UPLOADED: { text: 'Shared with your broker', className: 'text-muted' },
    PROCESSING: {
      text: 'Being read',
      className: 'text-amber-700',
      icon: <Loader2 className="h-3 w-3 animate-spin" />,
    },
    EXTRACTED: { text: 'Read by your broker', className: 'text-brand-500', icon: <Check className="h-3 w-3" /> },
    FAILED: { text: 'Could not be read', className: 'text-red-600' },
  }
  const m = meta[status]
  return (
    <span className={cn('flex items-center gap-1 text-[11px] font-medium', m.className)}>
      {m.icon}
      {m.text}
    </span>
  )
}
