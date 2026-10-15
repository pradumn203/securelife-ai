import { cn } from '@/lib/utils'

export interface TypingIndicatorProps {
  className?: string
}

/**
 * Three-dot bouncing indicator. Shown while we're waiting for the FIRST token
 * of an assistant reply; swap it out for the live-streaming bubble as soon as
 * tokens start arriving.
 */
export function TypingIndicator({ className }: TypingIndicatorProps) {
  return (
    <div
      aria-live="polite"
      aria-label="Assistant is typing"
      className={cn(
        'inline-flex items-center gap-1 rounded-2xl rounded-bl-sm border border-slate-200 bg-white px-4 py-3 shadow-sm',
        className
      )}
    >
      <Dot delay="0ms" />
      <Dot delay="150ms" />
      <Dot delay="300ms" />
    </div>
  )
}

function Dot({ delay }: { delay: string }) {
  return (
    <span
      className="inline-block h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400"
      style={{ animationDelay: delay, animationDuration: '1s' }}
    />
  )
}
