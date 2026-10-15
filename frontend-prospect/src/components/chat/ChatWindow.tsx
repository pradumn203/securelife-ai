import * as React from 'react'
import { MessageBubble, type BubbleRole } from './MessageBubble'
import { TypingIndicator } from './TypingIndicator'
import { cn } from '@/lib/utils'

export interface ChatWindowMessage {
  id: string
  role: BubbleRole
  content: string
  timestamp?: string
  /** Marks the message as currently being streamed. */
  streaming?: boolean
}

export interface ChatWindowProps {
  messages: ChatWindowMessage[]
  /** True when an assistant reply has been requested but no tokens have arrived yet. */
  awaitingFirstToken?: boolean
  className?: string
  /** Fired when the user clicks Retry on an ERROR bubble. */
  onRetry?: () => void
  /** Disables the Retry button while a retry is already in flight. */
  retrying?: boolean
}

/** How close (px) the user must be to the bottom for auto-scroll to kick in. */
const AUTOSCROLL_THRESHOLD = 100

export function ChatWindow({ messages, awaitingFirstToken, className, onRetry, retrying }: ChatWindowProps) {
  const scrollRef = React.useRef<HTMLDivElement>(null)
  const stickToBottomRef = React.useRef(true)

  // Keep the autoscroll decision up-to-date as the user scrolls.
  const handleScroll = React.useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight
    stickToBottomRef.current = distance < AUTOSCROLL_THRESHOLD
  }, [])

  // Scroll to bottom when messages or streaming state change — but only if the
  // user hasn't scrolled up to read older messages.
  React.useLayoutEffect(() => {
    if (!stickToBottomRef.current) return
    const el = scrollRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [messages, awaitingFirstToken])

  return (
    <div
      ref={scrollRef}
      onScroll={handleScroll}
      className={cn(
        'flex-1 overflow-y-auto scroll-smooth px-4 py-4 bg-slate-50/60',
        className
      )}
    >
      <div className="mx-auto flex max-w-2xl flex-col gap-4">
        {messages.length === 0 && !awaitingFirstToken && (
          <p className="text-center text-sm text-slate-400">
            Say hi to start the conversation.
          </p>
        )}

        {messages.map((m) => (
          <MessageBubble
            key={m.id}
            role={m.role}
            content={m.content}
            timestamp={m.timestamp}
            streaming={m.streaming}
            onRetry={m.role === 'ERROR' && onRetry ? onRetry : undefined}
            retrying={m.role === 'ERROR' ? retrying : undefined}
          />
        ))}

        {awaitingFirstToken && (
          <div className="flex flex-col items-start gap-1">
            <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-500">
              <span>SecureLife AI</span>
            </div>
            <TypingIndicator />
          </div>
        )}
      </div>
    </div>
  )
}
