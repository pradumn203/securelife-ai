import { ArrowRight, Check } from 'lucide-react'
import type { components } from '@/api/types'
import { STATUS_ORDER, statusLabel } from '@/components/pipeline/StatusBadge'
import { cn } from '@/lib/utils'
import { nextStep } from './pipelineGuide'

type Lead = components['schemas']['LeadDetailOut']

/**
 * The lead's position in the pipeline (New → In progress → Docs pending
 * review → Analysis complete → Closed) plus the one action that moves it on.
 */
export function PipelineStepper({ lead }: { lead: Lead }) {
  const current = STATUS_ORDER.indexOf(lead.status)
  return (
    <div className="space-y-2" data-testid="pipeline-stepper">
      <ol className="flex flex-wrap items-center gap-1.5 text-xs">
        {STATUS_ORDER.map((stage, i) => {
          const done = i < current
          const active = i === current
          return (
            <li key={stage} className="flex items-center gap-1.5">
              <span
                className={cn(
                  'inline-flex items-center gap-1 rounded-full border px-2.5 py-1 font-medium',
                  active && 'border-brand-600 bg-brand-600 text-white',
                  done && 'border-emerald-200 bg-emerald-50 text-emerald-700',
                  !active && !done && 'border-slate-200 bg-white text-slate-400'
                )}
                aria-current={active ? 'step' : undefined}
              >
                {done ? <Check className="h-3 w-3" aria-hidden="true" /> : null}
                {statusLabel(stage)}
              </span>
              {i < STATUS_ORDER.length - 1 ? (
                <ArrowRight className="h-3 w-3 text-slate-300" aria-hidden="true" />
              ) : null}
            </li>
          )
        })}
      </ol>
      <p className="text-xs text-slate-600" data-testid="next-step">
        <span className="font-semibold text-slate-900">Next step: </span>
        {nextStep(lead)}
      </p>
    </div>
  )
}
