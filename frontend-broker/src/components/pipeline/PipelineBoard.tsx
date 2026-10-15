import { Sparkles } from 'lucide-react'
import type { components } from '@/api/types'
import { LeadCard } from './LeadCard'

type Lead = components['schemas']['LeadOut']

export interface PipelineBoardProps {
  leads: Lead[]
  isLoading?: boolean
  error?: unknown
}

export function PipelineBoard({ leads, isLoading, error }: PipelineBoardProps) {
  if (isLoading && leads.length === 0) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="h-40 animate-pulse rounded-xl border border-slate-200 bg-white shadow-sm"
          />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">
        Could not reach the backend. Is <code className="rounded bg-red-100 px-1">uvicorn</code>{' '}
        running on port 8000?
      </div>
    )
  }

  if (leads.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white px-6 py-16 text-center">
        <Sparkles className="h-10 w-10 text-brand-500" />
        <h3 className="mt-4 text-base font-semibold text-slate-900">No prospects yet</h3>
        <p className="mt-1 max-w-sm text-sm text-slate-500">
          When a prospect chats with the SecureLife chat agent and shares their name and a
          contact detail, they'll show up here automatically.
        </p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {leads.map((lead) => (
        <LeadCard key={lead.id} lead={lead} />
      ))}
    </div>
  )
}
