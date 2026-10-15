import type { components } from '@/api/types'
import { Separator } from '@/components/ui/separator'
import { EvidenceTooltip } from './EvidenceTooltip'

type DocumentExtractionOut = components['schemas']['DocumentExtractionOut']
type FieldEvidence = components['schemas']['FieldEvidence']

export interface ExtractionPanelProps {
  extraction: DocumentExtractionOut
}

/** INR formatter — no decimals, Indian lakh/crore grouping. */
const inr = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
})

const dateFmt = new Intl.DateTimeFormat('en-GB', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
})

const toNumber = (v: string | null | undefined): number | null => {
  if (v === null || v === undefined || v === '') return null
  const n = Number(String(v).replace(/,/g, ''))
  return Number.isFinite(n) ? n : null
}

const formatRenewal = (iso: string | null | undefined): string | null => {
  if (!iso) return null
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return dateFmt.format(d)
}

interface FieldRow {
  key: string
  label: string
  value: string | null
}

/** Build the ordered list of display rows from the raw extraction. */
const buildRows = (e: DocumentExtractionOut): FieldRow[] => {
  const sum = toNumber(e.sum_insured ?? null)
  const premium = toNumber(e.premium_amount ?? null)
  return [
    { key: 'policy_type', label: 'Policy type', value: e.policy_type ?? null },
    { key: 'provider', label: 'Provider', value: e.provider ?? null },
    { key: 'policy_number', label: 'Policy number', value: e.policy_number ?? null },
    { key: 'insured_name', label: 'Insured', value: e.insured_name ?? null },
    {
      key: 'sum_insured',
      label: 'Sum insured',
      value: sum !== null ? inr.format(sum) : null,
    },
    {
      key: 'premium_amount',
      label: 'Premium',
      value: premium !== null ? inr.format(premium) : null,
    },
    {
      key: 'premium_frequency',
      label: 'Premium frequency',
      value: e.premium_frequency ?? null,
    },
    {
      key: 'renewal_date',
      label: 'Renewal',
      value: formatRenewal(e.renewal_date ?? null),
    },
  ]
}

export function ExtractionPanel({ extraction }: ExtractionPanelProps) {
  const rows = buildRows(extraction)
  const evidence = (extraction.evidence ?? {}) as Record<string, FieldEvidence>
  const exclusions = (extraction.exclusions ?? []) as Array<{
    text?: string
    source_page?: number | null
  }>
  const riders = (extraction.riders ?? []) as Array<{
    name?: string
    description?: string | null
    source_page?: number | null
  }>
  return (
    <div className="space-y-5">
      <div>
        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
          Extracted fields
        </h4>
        <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
          {rows.map((row) => {
            const ev = evidence[row.key] ?? null
            const missing = row.value === null
            return (
              <div
                key={row.key}
                className="flex flex-col gap-1 border-b border-slate-100 pb-2 last:border-0 sm:last:border-b"
              >
                <dt className="text-xs font-medium text-slate-500">{row.label}</dt>
                <dd className="flex items-center justify-between gap-3">
                  <span
                    className={
                      missing
                        ? 'text-sm text-slate-400'
                        : 'text-sm font-medium text-slate-900'
                    }
                  >
                    {row.value ?? '—'}
                  </span>
                  <EvidenceTooltip evidence={ev} isMissing={missing} />
                </dd>
              </div>
            )
          })}
        </dl>
      </div>

      {exclusions.length > 0 ? (
        <>
          <Separator />
          <div>
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Exclusions ({exclusions.length})
            </h4>
            <ul className="space-y-1.5 text-sm text-slate-700">
              {exclusions.map((ex, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span
                    aria-hidden="true"
                    className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400"
                  />
                  <span>
                    {ex.text ?? '—'}
                    {typeof ex.source_page === 'number' ? (
                      <span className="ml-2 text-xs text-slate-400">
                        p.{ex.source_page}
                      </span>
                    ) : null}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </>
      ) : null}

      {riders.length > 0 ? (
        <>
          <Separator />
          <div>
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Riders ({riders.length})
            </h4>
            <ul className="space-y-2 text-sm text-slate-700">
              {riders.map((r, i) => (
                <li key={i} className="rounded-md border border-slate-100 bg-slate-50 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-slate-900">
                      {r.name ?? 'Rider'}
                    </span>
                    {typeof r.source_page === 'number' ? (
                      <span className="text-xs text-slate-400">p.{r.source_page}</span>
                    ) : null}
                  </div>
                  {r.description ? (
                    <p className="mt-1 text-sm text-slate-600">{r.description}</p>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        </>
      ) : null}
    </div>
  )
}
