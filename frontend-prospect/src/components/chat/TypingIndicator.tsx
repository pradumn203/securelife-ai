import { BrandMark } from '@/components/layout/BrandMark'

/**
 * Shown while waiting for the FIRST token of a reply: the assistant's mark
 * with three soft dots, replaced by the streaming text once tokens arrive.
 */
export function TypingIndicator() {
  return (
    <div className="flex gap-4" aria-live="polite" aria-label="Assistant is typing">
      <BrandMark />
      <div className="flex items-center gap-1.5 pt-0.5">
        <Dot delay="0ms" />
        <Dot delay="160ms" />
        <Dot delay="320ms" />
      </div>
    </div>
  )
}

function Dot({ delay }: { delay: string }) {
  return (
    <span
      className="inline-block h-2 w-2 animate-pulse rounded-full bg-muted/60"
      style={{ animationDelay: delay, animationDuration: '1.2s' }}
    />
  )
}
