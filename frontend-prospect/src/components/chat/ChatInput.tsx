import * as React from 'react'
import { ArrowUp, Square } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface ChatInputProps {
  onSend: (message: string) => void
  disabled?: boolean
  /** When true, show a Stop button so the user can abort a streaming reply. */
  streaming?: boolean
  onStop?: () => void
  placeholder?: string
  /** Rendered above the text box (attached files). */
  attachments?: React.ReactNode
  /** Rendered bottom-left inside the box (the attach button). */
  tools?: React.ReactNode
  /** A PDF dropped onto the composer. */
  onDropFile?: (file: File) => void
}

const MAX_HEIGHT_PX = 200

/**
 * The composer, ChatGPT / Claude style: one rounded box pinned to the bottom
 * of the page with the text area, tools on the left and a round send button.
 * Enter sends, Shift+Enter adds a line.
 */
export function ChatInput({
  onSend,
  disabled,
  streaming,
  onStop,
  placeholder = 'Message SecureLife',
  attachments,
  tools,
  onDropFile,
}: ChatInputProps) {
  const [value, setValue] = React.useState('')
  const [dragOver, setDragOver] = React.useState(false)
  const textareaRef = React.useRef<HTMLTextAreaElement>(null)

  // Auto-grow with the content, up to a cap.
  React.useLayoutEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT_PX)}px`
  }, [value])

  // Focus the box once the session is ready, and after each reply.
  React.useEffect(() => {
    if (!disabled && !streaming) textareaRef.current?.focus()
  }, [disabled, streaming])

  const submit = () => {
    const trimmed = value.trim()
    if (!trimmed || disabled || streaming) return
    onSend(trimmed)
    setValue('')
  }

  const canSend = value.trim().length > 0 && !disabled && !streaming

  return (
    <div
      className={cn(
        'rounded-[28px] border bg-white p-2 shadow-[0_1px_2px_rgba(21,23,21,0.04),0_10px_30px_-12px_rgba(21,23,21,0.18)] transition-colors focus-within:border-ink/25',
        dragOver ? 'border-ink/40 bg-brand-50' : 'border-line'
      )}
      onDragOver={(e) => {
        if (!onDropFile) return
        e.preventDefault()
        setDragOver(true)
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        if (!onDropFile) return
        e.preventDefault()
        setDragOver(false)
        const file = e.dataTransfer.files?.[0]
        if (file) onDropFile(file)
      }}
    >
      {attachments}
      <textarea
        ref={textareaRef}
        rows={1}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault()
            submit()
          }
        }}
        placeholder={placeholder}
        disabled={disabled}
        aria-label="Message"
        className="block max-h-[200px] w-full resize-none bg-transparent px-3 pb-1 pt-2.5 text-[15px] leading-6 text-ink outline-none placeholder:text-muted disabled:cursor-not-allowed"
      />
      <div className="flex items-center justify-between gap-2 pl-1">
        <div className="min-w-0">{tools}</div>
        {streaming ? (
          <button
            type="button"
            onClick={onStop}
            aria-label="Stop the reply"
            title="Stop"
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ink text-white hover:bg-ink-2"
          >
            <Square className="h-3.5 w-3.5 fill-current" />
          </button>
        ) : (
          <button
            type="button"
            onClick={submit}
            disabled={!canSend}
            aria-label="Send message"
            title="Send (Enter)"
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ink text-white transition-colors hover:bg-ink-2 disabled:bg-mist disabled:text-muted"
          >
            <ArrowUp className="h-[18px] w-[18px]" strokeWidth={2.5} />
          </button>
        )}
      </div>
    </div>
  )
}
