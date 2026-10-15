import { Bot, User, AlertTriangle, RotateCcw } from 'lucide-react'
import { cn } from '@/lib/utils'

export type BubbleRole = 'USER' | 'ASSISTANT' | 'SYSTEM' | 'ERROR'

export interface MessageBubbleProps {
  role: BubbleRole
  content: string
  /** Optional ISO timestamp for a subtle meta line. */
  timestamp?: string
  /** Show a soft pulse while the assistant is still streaming. */
  streaming?: boolean
  /** Shown instead of content while the first token hasn't arrived yet. */
  placeholder?: React.ReactNode
  /** When role=ERROR, show a Retry button that calls this handler. */
  onRetry?: () => void
  /** Disables the Retry button while a retry is already in flight. */
  retrying?: boolean
}

const ROLE_META: Record<
  BubbleRole,
  { label: string; icon: React.ComponentType<{ className?: string }>; align: 'left' | 'right' }
> = {
  USER: { label: 'You', icon: User, align: 'right' },
  ASSISTANT: { label: 'SecureLife AI', icon: Bot, align: 'left' },
  SYSTEM: { label: 'System', icon: Bot, align: 'left' },
  ERROR: { label: 'Error', icon: AlertTriangle, align: 'left' },
}

export function MessageBubble({
  role,
  content,
  timestamp,
  streaming,
  placeholder,
  onRetry,
  retrying,
}: MessageBubbleProps) {
  const meta = ROLE_META[role]
  const Icon = meta.icon
  const isUser = role === 'USER'
  const isError = role === 'ERROR'

  const bubbleClasses = cn(
    'inline-block max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words shadow-sm',
    isUser && 'bg-brand-600 text-white rounded-br-sm',
    role === 'ASSISTANT' && 'bg-white text-slate-900 border border-slate-200 rounded-bl-sm',
    role === 'SYSTEM' && 'bg-slate-100 text-slate-700 rounded-bl-sm',
    isError && 'bg-red-50 text-red-800 border border-red-200 rounded-bl-sm',
    streaming && 'animate-[pulse_2.5s_ease-in-out_infinite]'
  )

  return (
    <div className={cn('flex w-full flex-col gap-1', isUser ? 'items-end' : 'items-start')}>
      <div
        className={cn(
          'flex items-center gap-1.5 text-[11px] font-medium text-slate-500',
          isUser && 'flex-row-reverse'
        )}
      >
        <Icon className={cn('h-3 w-3', isError && 'text-red-600')} />
        <span>{meta.label}</span>
        {timestamp && <span className="text-slate-400">· {formatTime(timestamp)}</span>}
      </div>
      <div className={bubbleClasses}>
        {content.length > 0 ? content : placeholder ?? ' '}
      </div>
      {isError && onRetry && (
        <button
          type="button"
          onClick={onRetry}
          disabled={retrying}
          className={cn(
            'mt-1 inline-flex items-center gap-1 rounded-md border border-red-200 bg-white px-2.5 py-1 text-[11px] font-medium text-red-700',
            'hover:bg-red-50 hover:border-red-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400',
            'disabled:cursor-not-allowed disabled:opacity-60'
          )}
          aria-label="Retry the last message"
        >
          <RotateCcw
            className={cn('h-3 w-3', retrying && 'animate-spin')}
            aria-hidden="true"
          />
          {retrying ? 'Retrying…' : 'Retry'}
        </button>
      )}
    </div>
  )
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return ''
    return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}
