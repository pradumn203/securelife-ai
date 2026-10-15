import { AlertCircle, RotateCcw } from 'lucide-react'
import { BrandMark } from '@/components/layout/BrandMark'
import { cn } from '@/lib/utils'

export type BubbleRole = 'USER' | 'ASSISTANT' | 'SYSTEM' | 'ERROR'

export interface MessageBubbleProps {
  role: BubbleRole
  content: string
  /** Show a blinking caret while the assistant is still streaming. */
  streaming?: boolean
  /** When role=ERROR, show a Retry button that calls this handler. */
  onRetry?: () => void
  /** Disables the Retry button while a retry is already in flight. */
  retrying?: boolean
}

/**
 * One turn of the conversation, laid out like ChatGPT / Claude: the prospect's
 * messages sit in a soft bubble on the right, the assistant's replies are
 * plain text beside the SecureLife mark.
 */
export function MessageBubble({ role, content, streaming, onRetry, retrying }: MessageBubbleProps) {
  if (role === 'USER') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-3xl bg-mist px-5 py-3 text-[15px] leading-7 text-ink sm:max-w-[75%]">
          {content}
        </div>
      </div>
    )
  }

  if (role === 'ERROR') {
    return (
      <div className="flex gap-4">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-red-50">
          <AlertCircle className="h-4 w-4 text-red-600" aria-hidden="true" />
        </span>
        <div className="min-w-0 pt-1 text-[15px] leading-7">
          <p className="text-red-700">{content}</p>
          {onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              disabled={retrying}
              className="mt-2 inline-flex items-center gap-1.5 rounded-full border border-line bg-white px-3 py-1.5 text-xs font-semibold text-ink-2 hover:bg-mist disabled:cursor-not-allowed disabled:opacity-60"
              aria-label="Retry the last message"
            >
              <RotateCcw className={cn('h-3.5 w-3.5', retrying && 'animate-spin')} aria-hidden="true" />
              {retrying ? 'Retrying…' : 'Try again'}
            </button>
          ) : null}
        </div>
      </div>
    )
  }

  return (
    <div className="flex gap-4">
      <BrandMark />
      <div
        className={cn(
          'min-w-0 flex-1 whitespace-pre-wrap break-words pt-0.5 text-[15px] leading-7',
          role === 'SYSTEM' ? 'text-muted' : 'text-ink',
          streaming && 'stream-caret'
        )}
      >
        {content}
      </div>
    </div>
  )
}
