import * as React from 'react'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * Minimal headless Dialog. Uses the native <dialog> element for modal
 * semantics + focus trap, with Tailwind styling on top.
 */
export interface DialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  children: React.ReactNode
  className?: string
  title?: React.ReactNode
  description?: React.ReactNode
}

export function Dialog({ open, onOpenChange, children, className, title, description }: DialogProps) {
  const ref = React.useRef<HTMLDialogElement | null>(null)

  React.useEffect(() => {
    const dlg = ref.current
    if (!dlg) return
    if (open && !dlg.open) {
      dlg.showModal()
    } else if (!open && dlg.open) {
      dlg.close()
    }
  }, [open])

  const handleCancel = React.useCallback(
    (event: React.SyntheticEvent<HTMLDialogElement>) => {
      event.preventDefault()
      onOpenChange(false)
    },
    [onOpenChange]
  )

  const handleBackdropClick = React.useCallback(
    (event: React.MouseEvent<HTMLDialogElement>) => {
      if (event.target === event.currentTarget) {
        onOpenChange(false)
      }
    },
    [onOpenChange]
  )

  return (
    <dialog
      ref={ref}
      onCancel={handleCancel}
      onClick={handleBackdropClick}
      className={cn(
        'rounded-xl border border-slate-200 bg-white p-0 shadow-2xl backdrop:bg-slate-950/40 backdrop:backdrop-blur-sm',
        'open:animate-in open:fade-in-0 w-[32rem] max-w-[90vw]',
        className
      )}
    >
      <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
        <div>
          {title && <h2 className="text-base font-semibold text-slate-900">{title}</h2>}
          {description && <p className="mt-0.5 text-sm text-slate-500">{description}</p>}
        </div>
        <button
          type="button"
          onClick={() => onOpenChange(false)}
          aria-label="Close dialog"
          className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="p-5">{children}</div>
    </dialog>
  )
}

export function DialogFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('mt-6 flex items-center justify-end gap-2 border-t border-slate-100 pt-4', className)}
      {...props}
    />
  )
}
