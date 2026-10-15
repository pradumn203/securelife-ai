import * as React from 'react'
import { UploadCloud, X } from 'lucide-react'
import { Progress } from '@/components/ui/progress'
import { cn } from '@/lib/utils'

export interface DocumentUploadProps {
  /** Called with the user-selected PDF File. Non-PDF files are rejected locally. */
  onUpload: (file: File) => Promise<void> | void
  /** True while a mutation is in flight; disables the dropzone + file picker. */
  isUploading?: boolean
  /** Server-side error from the latest attempt, if any. */
  errorMessage?: string | null
}

const ACCEPT = 'application/pdf'

/**
 * Drag-and-drop + file-picker upload well. Only accepts a single PDF per
 * invocation; the parent decides how to show the resulting card.
 */
export function DocumentUpload({
  onUpload,
  isUploading,
  errorMessage,
}: DocumentUploadProps) {
  const inputRef = React.useRef<HTMLInputElement | null>(null)
  const [dragOver, setDragOver] = React.useState(false)
  const [localError, setLocalError] = React.useState<string | null>(null)

  const handleFile = React.useCallback(
    async (file: File | null) => {
      if (!file) return
      setLocalError(null)
      if (file.type !== ACCEPT) {
        setLocalError('Only PDF files are supported.')
        return
      }
      await onUpload(file)
      if (inputRef.current) inputRef.current.value = ''
    },
    [onUpload]
  )

  const onDrop = React.useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault()
      setDragOver(false)
      const file = e.dataTransfer?.files?.[0] ?? null
      void handleFile(file)
    },
    [handleFile]
  )

  const onInputChange = React.useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0] ?? null
      void handleFile(file)
    },
    [handleFile]
  )

  const openPicker = React.useCallback(() => {
    if (isUploading) return
    inputRef.current?.click()
  }, [isUploading])

  const errorText = localError ?? errorMessage ?? null

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload policy PDF"
        aria-disabled={isUploading}
        onClick={openPicker}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            openPicker()
          }
        }}
        onDragEnter={(e) => {
          e.preventDefault()
          if (!isUploading) setDragOver(true)
        }}
        onDragOver={(e) => {
          e.preventDefault()
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        className={cn(
          'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-6 text-center transition-colors',
          dragOver
            ? 'border-brand-500 bg-brand-50/70'
            : 'border-slate-300 bg-slate-50 hover:border-brand-400 hover:bg-brand-50/40',
          isUploading && 'pointer-events-none opacity-70'
        )}
      >
        <div
          className={cn(
            'flex h-10 w-10 items-center justify-center rounded-full',
            dragOver ? 'bg-brand-100 text-brand-700' : 'bg-white text-brand-600'
          )}
        >
          <UploadCloud className="h-5 w-5" aria-hidden="true" />
        </div>
        <div>
          <p className="text-sm font-medium text-slate-900">
            {dragOver ? 'Drop to upload' : 'Drop a policy PDF or click to browse'}
          </p>
          <p className="text-xs text-slate-500">
            PDF only · up to a few megabytes
          </p>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          className="hidden"
          onChange={onInputChange}
          disabled={isUploading}
        />
      </div>

      {isUploading ? (
        <div className="mt-3">
          <Progress value={75} aria-label="Uploading" />
          <p className="mt-1 text-xs text-slate-500">Uploading…</p>
        </div>
      ) : null}

      {errorText ? (
        <div className="mt-3 flex items-start justify-between gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          <span>{errorText}</span>
          <button
            type="button"
            onClick={() => setLocalError(null)}
            className="shrink-0 rounded p-0.5 text-red-600 hover:bg-red-100"
            aria-label="Dismiss error"
          >
            <X className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        </div>
      ) : null}
    </div>
  )
}
