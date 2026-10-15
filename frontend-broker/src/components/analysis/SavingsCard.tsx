import { TrendingDown } from 'lucide-react'
import type { components } from '@/api/types'
import { cn } from '@/lib/utils'

type PotentialSavings = components['schemas']['PotentialSavings']

export interface SavingsCardProps {
  savings: PotentialSavings
}

const inr = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
})

/**
 * The backend only keeps a savings figure when a verified premium in the
 * policy documents supports it (`basis: verified_premium`). Otherwise the
 * card says "Not quantified" and shows why, instead of a number.
 */
export function SavingsCard({ savings }: SavingsCardProps) {
  const amount = Number(savings.annual_inr ?? 0)
  const quantified = savings.basis !== 'not_quantified' && Number.isFinite(amount) && amount > 0
  return (
    <div
      className={cn(
        'rounded-xl border p-4',
        quantified ? 'border-emerald-200 bg-emerald-50/60' : 'border-slate-200 bg-white'
      )}
    >
      <div className="flex items-start gap-3">
        <div
          className={cn(
            'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg shadow-sm',
            quantified ? 'bg-white text-emerald-700' : 'bg-slate-50 text-slate-400'
          )}
        >
          <TrendingDown className="h-5 w-5" aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <p
            className={cn(
              'text-xs font-medium uppercase tracking-wide',
              quantified ? 'text-emerald-700' : 'text-slate-500'
            )}
          >
            Potential annual savings
          </p>
          {quantified ? (
            <>
              <p className="mt-0.5 text-2xl font-semibold text-emerald-900">{inr.format(amount)}</p>
              <p className="text-[11px] text-emerald-800/80">
                Estimate based on the verified premium in the policy document.
              </p>
            </>
          ) : (
            <p className="mt-0.5 text-lg font-semibold text-slate-700">Not quantified</p>
          )}
          {savings.rationale ? (
            <p className={cn('mt-2 text-sm', quantified ? 'text-emerald-900/80' : 'text-slate-600')}>
              {savings.rationale}
            </p>
          ) : null}
        </div>
      </div>
    </div>
  )
}
