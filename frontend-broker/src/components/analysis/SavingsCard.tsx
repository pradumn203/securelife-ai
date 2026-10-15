import { TrendingDown } from 'lucide-react'
import type { components } from '@/api/types'

type PotentialSavings = components['schemas']['PotentialSavings']

export interface SavingsCardProps {
  savings: PotentialSavings
}

const inr = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
})

export function SavingsCard({ savings }: SavingsCardProps) {
  const amount = Number(savings.annual_inr ?? 0)
  const formatted = Number.isFinite(amount) ? inr.format(amount) : '—'
  return (
    <div className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-4">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white text-emerald-700 shadow-sm">
          <TrendingDown className="h-5 w-5" aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium uppercase tracking-wide text-emerald-700">
            Potential annual savings
          </p>
          <p className="mt-0.5 text-2xl font-semibold text-emerald-900">
            {formatted}
          </p>
          {savings.rationale ? (
            <p className="mt-2 text-sm text-emerald-900/80">
              {savings.rationale}
            </p>
          ) : null}
        </div>
      </div>
    </div>
  )
}
