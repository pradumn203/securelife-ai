import { Info } from 'lucide-react'
import type { components } from '@/api/types'
import { cn } from '@/lib/utils'
import { Tooltip } from '@/components/ui/tooltip'

type FieldEvidence = components['schemas']['FieldEvidence']

export interface EvidenceTooltipProps {
  /** The evidence record for this field, if present. */
  evidence?: FieldEvidence | null
  /**
   * Whether the extracted value for this field is `null` / absent. Changes
   * the pill colour + tooltip copy ("not present" vs. a page citation).
   */
  isMissing?: boolean
  className?: string
}

const formatConfidence = (c: number): string => {
  const pct = Math.round(c * 100)
  return `${pct}%`
}

/**
 * Hover-only pill that reveals the source page / excerpt / confidence a
 * single extracted field was drawn from. Keeps the field grid uncluttered.
 */
export function EvidenceTooltip({
  evidence,
  isMissing,
  className,
}: EvidenceTooltipProps) {
  if (isMissing || !evidence) {
    return (
      <Tooltip
        side="top"
        content={
          <span className="block text-slate-500">
            Field not present in the source document.
          </span>
        }
      >
        <span
          className={cn(
            'inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-500',
            className
          )}
        >
          <Info className="h-3 w-3" aria-hidden="true" />
          not present
        </span>
      </Tooltip>
    )
  }
  const page = evidence.source_page ?? null
  const excerpt = evidence.source_excerpt ?? ''
  const confidence = formatConfidence(evidence.confidence ?? 0)
  return (
    <Tooltip
      side="top"
      content={
        <div className="space-y-1.5">
          <div className="flex items-center justify-between gap-3 text-[10px] font-medium uppercase tracking-wide text-slate-500">
            <span>Page {page ?? '—'}</span>
            <span>Confidence {confidence}</span>
          </div>
          {excerpt ? (
            <blockquote className="border-l-2 border-brand-500 pl-2 text-xs italic text-slate-700">
              “{excerpt}”
            </blockquote>
          ) : (
            <p className="text-xs text-slate-500">No excerpt captured.</p>
          )}
        </div>
      }
    >
      <span
        className={cn(
          'inline-flex items-center gap-1 rounded-full border border-brand-100 bg-brand-50 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-brand-700',
          className
        )}
      >
        <Info className="h-3 w-3" aria-hidden="true" />
        p.{page ?? '—'} · {confidence}
      </span>
    </Tooltip>
  )
}
