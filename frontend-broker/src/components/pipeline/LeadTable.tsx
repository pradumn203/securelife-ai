import { useNavigate, Link } from 'react-router-dom'
import { Inbox } from 'lucide-react'
import type { components } from '@/api/types'
import { INSURANCE_TYPE_LABEL } from '@/components/leads/profileLabels'
import { CLOSE_REASON_LABEL, StatusBadge } from './StatusBadge'
import { cn } from '@/lib/utils'

type Lead = components['schemas']['LeadOut']
type Verdict = NonNullable<Lead['qualification_verdict']>

export interface LeadTableProps {
  leads: Lead[]
  isLoading?: boolean
  error?: unknown
}

const VERDICT_CHIP: Record<Verdict, { label: string; className: string }> = {
  QUALIFIED: { label: 'Qualified', className: 'bg-lime text-lime-ink' },
  NOT_QUALIFIED: { label: 'Not qualified', className: 'bg-red-100 text-red-800' },
  NEEDS_MORE_INFO: { label: 'Needs more info', className: 'bg-amber-100 text-amber-900' },
}

const AVATAR_TONES = ['bg-lime text-lime-ink', 'bg-lavender text-lavender-ink', 'bg-ink text-white', 'bg-mist text-ink']

/** Humanise an ISO timestamp into "3h ago" / "2d ago" style. */
function relativeTime(iso: string): string {
  const seconds = Math.max(1, Math.floor((Date.now() - new Date(iso).getTime()) / 1000))
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d ago`
  const months = Math.floor(days / 30)
  return months < 12 ? `${months}mo ago` : `${Math.floor(days / 365)}y ago`
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  return ((parts[0]?.[0] ?? '?') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase()
}

function toneFor(id: string): string {
  let hash = 0
  for (const ch of id) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0
  return AVATAR_TONES[hash % AVATAR_TONES.length]
}

/** The broker's lead list: one row per prospect, the whole row opens the lead. */
export function LeadTable({ leads, isLoading, error }: LeadTableProps) {
  const navigate = useNavigate()

  if (error) {
    return (
      <div className="m-4 rounded-2xl bg-red-50 p-5 text-sm text-red-800">
        Could not reach the backend. Is <code className="rounded bg-red-100 px-1">uvicorn</code> running on
        port 8000?
      </div>
    )
  }

  if (isLoading && leads.length === 0) {
    return (
      <div className="space-y-2 p-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-14 animate-pulse rounded-2xl bg-mist" />
        ))}
      </div>
    )
  }

  if (leads.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
        <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-mist">
          <Inbox className="h-5 w-5 text-muted" aria-hidden="true" />
        </span>
        <h3 className="mt-4 text-base font-bold text-ink">No prospects here</h3>
        <p className="mt-1 max-w-sm text-sm text-muted">
          Prospects appear once they've shared a name and a phone number or email in the chat.
        </p>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] border-separate border-spacing-0 text-sm">
        <thead>
          <tr className="text-left text-xs font-semibold text-muted">
            <th className="px-5 py-3 font-semibold">Prospect</th>
            <th className="hidden px-3 py-3 font-semibold lg:table-cell">Cover</th>
            <th className="px-3 py-3 font-semibold">Stage</th>
            <th className="px-3 py-3 font-semibold">Qualification</th>
            <th className="hidden px-3 py-3 font-semibold xl:table-cell">City</th>
            <th className="hidden px-5 py-3 text-right font-semibold md:table-cell">Added</th>
          </tr>
        </thead>
        <tbody>
          {leads.map((lead) => {
            const name = lead.full_name ?? 'Unnamed prospect'
            const contact = lead.email ?? lead.phone ?? null
            const verdict = lead.qualification_verdict ?? null
            const insurance = lead.extracted_fields?.insurance_type ?? null
            return (
              <tr
                key={lead.id}
                onClick={() => navigate(`/leads/${lead.id}`)}
                className="group cursor-pointer [&>td]:border-t [&>td]:border-mist hover:[&>td]:bg-mist/70"
              >
                <td className="rounded-l-2xl px-5 py-3">
                  <div className="flex items-center gap-3">
                    <span
                      className={cn(
                        'flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-bold',
                        toneFor(lead.id)
                      )}
                      aria-hidden="true"
                    >
                      {initials(name)}
                    </span>
                    <div className="min-w-0">
                      <Link
                        to={`/leads/${lead.id}`}
                        onClick={(e) => e.stopPropagation()}
                        className="block truncate font-bold text-ink focus:outline-none focus-visible:underline"
                      >
                        {name}
                      </Link>
                      <span className="block truncate text-xs text-muted">{contact ?? 'No contact yet'}</span>
                    </div>
                  </div>
                </td>
                <td className="hidden px-3 py-3 font-medium text-ink-2 lg:table-cell">
                  {insurance ? (INSURANCE_TYPE_LABEL[insurance] ?? insurance) : <span className="text-muted">—</span>}
                </td>
                <td className="px-3 py-3">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <StatusBadge status={lead.status} />
                    {lead.status === 'CLOSED' && lead.close_reason ? (
                      <span className="text-xs font-medium text-muted">{CLOSE_REASON_LABEL[lead.close_reason]}</span>
                    ) : null}
                  </div>
                </td>
                <td className="px-3 py-3">
                  {verdict ? (
                    <div className="flex items-center gap-2">
                      <span className="w-7 text-right font-bold tabular-nums text-ink">{lead.qualification_score}</span>
                      <span
                        className={cn(
                          'rounded-full px-2.5 py-0.5 text-xs font-semibold',
                          VERDICT_CHIP[verdict].className
                        )}
                      >
                        {VERDICT_CHIP[verdict].label}
                      </span>
                    </div>
                  ) : (
                    <span className="text-xs font-medium text-muted">
                      Not run · profile {lead.profile_completeness}%
                    </span>
                  )}
                </td>
                <td className="hidden px-3 py-3 text-ink-2 xl:table-cell">{lead.city ?? <span className="text-muted">—</span>}</td>
                <td className="hidden rounded-r-2xl px-5 py-3 text-right text-xs font-medium text-muted md:table-cell">
                  {relativeTime(lead.created_at)}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
