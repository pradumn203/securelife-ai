import * as React from 'react'
import { Send, Square } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'

export interface ChatInputProps {
  onSend: (message: string) => void
  disabled?: boolean
  /** When true, show a Stop button so the user can abort a streaming reply. */
  streaming?: boolean
  onStop?: () => void
  placeholder?: string
}

const MAX_ROWS = 8

export function ChatInput({
  onSend,
  disabled,
  streaming,
  onStop,
  placeholder = 'Type a message… (Shift+Enter for newline)',
}: ChatInputProps) {
  const [value, setValue] = React.useState('')
  const textareaRef = React.useRef<HTMLTextAreaElement>(null)

  // Auto-grow the textarea with the content, capped at MAX_ROWS lines.
  React.useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    const lineHeight = 20 // ~text-sm leading-relaxed
    const maxHeight = lineHeight * MAX_ROWS + 20 // +padding
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`
  }, [value])

  const submit = () => {
    const trimmed = value.trim()
    if (!trimmed || disabled || streaming) return
    onSend(trimmed)
    setValue('')
    // Reset height on next tick after state flushes.
    requestAnimationFrame(() => {
      if (textareaRef.current) textareaRef.current.style.height = 'auto'
    })
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const canSend = value.trim().length > 0 && !disabled && !streaming

  return (
    <div className="flex items-end gap-2 border-t border-slate-200 bg-white p-3">
      <Textarea
        ref={textareaRef}
        rows={1}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        className={cn('max-h-48 flex-1 leading-relaxed')}
      />
      {streaming ? (
        <Button
          type="button"
          variant="outline"
          size="icon"
          onClick={onStop}
          aria-label="Stop streaming"
          title="Stop generating"
        >
          <Square className="h-4 w-4" />
        </Button>
      ) : (
        <Button
          type="button"
          size="icon"
          onClick={submit}
          disabled={!canSend}
          aria-label="Send message"
          title="Send (Enter)"
        >
          <Send className="h-4 w-4" />
        </Button>
      )}
    </div>
  )
}
