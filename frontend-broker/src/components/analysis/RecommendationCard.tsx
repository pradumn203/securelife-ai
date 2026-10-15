import { Flag } from 'lucide-react'
import type { components } from '@/api/types'

type AnalysisOut = components['schemas']['AnalysisOut']

export interface RecommendationCardProps {
  analysis: AnalysisOut
}

const dateFmt = new Intl.DateTimeFormat('en-GB', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

/**
 * Backend `AnalysisOut.confidence` is an int in [0, 100] (see analysis
 * schema), not a 0–1 ratio like `FieldEvidence.confidence`. Guard against
 * out-of-range values just in case.
 */
const formatConfidence = (c: number): string => {
  const pct = Math.max(0, Math.min(100, Math.round(c)))
  return `${pct}%`
}

export function RecommendationCard({ analysis }: RecommendationCardProps) {
  const created = (() => {
    const d = new Date(analysis.created_at)
    return Number.isNaN(d.getTime()) ? analysis.created_at : dateFmt.format(d)
  })()
  return (
    <div className="relative overflow-hidden rounded-xl border-2 border-brand-300 bg-gradient-to-br from-brand-50 via-white to-brand-50/40 p-5 shadow-md">
      <div className="pointer-events-none absolute -right-8 -top-8 h-28 w-28 rounded-full bg-brand-100 opacity-50" />
      <div className="relative">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-brand-700">
            <Flag className="h-4 w-4" aria-hidden="true" />
            Final recommendation
          </div>
          <span className="rounded-full bg-brand-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-brand-800">
            Broker-ready
          </span>
        </div>
        <blockquote className="mt-3 border-l-4 border-brand-500 pl-4 text-base font-semibold leading-relaxed text-slate-900">
          {analysis.recommended_action}
        </blockquote>
        <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
          <span>
            Model <span className="font-medium text-slate-700">{analysis.model_name}</span>
          </span>
          <span className="h-1 w-1 rounded-full bg-slate-300" aria-hidden="true" />
          <span>
            Confidence{' '}
            <span className="font-medium text-slate-700">
              {formatConfidence(analysis.confidence)}
            </span>
          </span>
          <span className="h-1 w-1 rounded-full bg-slate-300" aria-hidden="true" />
          <span>{created}</span>
        </div>
      </div>
    </div>
  )
}
