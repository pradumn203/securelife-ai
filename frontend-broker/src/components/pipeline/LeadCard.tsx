import { Link } from 'react-router-dom'
import { MapPin, Mail, Phone, Clock } from 'lucide-react'
import type { components } from '@/api/types'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { ScoreBar } from './ScoreBar'
import { CLOSE_REASON_LABEL, StatusBadge } from './StatusBadge'
import { cn } from '@/lib/utils'

type Lead = components['schemas']['LeadOut']

export interface LeadCardProps {
  lead: Lead
}

/** Humanize an ISO timestamp into "3h ago" / "2d ago" style. */
function relativeTime(iso: string): string {
  const then = new Date(iso).getTime()
  const now = Date.now()
  const seconds = Math.max(1, Math.floor((now - then) / 1000))
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d ago`
  const months = Math.floor(days / 30)
  if (months < 12) return `${months}mo ago`
  const years = Math.floor(days / 365)
  return `${years}y ago`
}

type Verdict = NonNullable<Lead['qualification_verdict']>

const VERDICT_CHIP: Record<Verdict, { label: string; className: string }> = {
  QUALIFIED: { label: 'Qualified', className: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  NOT_QUALIFIED: { label: 'Not qualified', className: 'bg-red-50 text-red-700 border-red-200' },
  NEEDS_MORE_INFO: { label: 'Needs more info', className: 'bg-amber-50 text-amber-800 border-amber-200' },
}

export function LeadCard({ lead }: LeadCardProps) {
  const name = lead.full_name ?? 'Unnamed prospect'
  const contactIcon = lead.email ? Mail : lead.phone ? Phone : null
  const contact = lead.email ?? lead.phone ?? null
  // Until the qualification agent runs, the useful number is how much of the
  // question plan the chat has captured; afterwards it's the agent's score.
  const verdict = lead.qualification_verdict ?? null
  const isPreQualification = verdict === null

  return (
    <Link
      to={`/leads/${lead.id}`}
      className="group block focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 rounded-xl"
    >
      <Card className="h-full transition-all group-hover:border-brand-200 group-hover:shadow-md">
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h3 className="truncate text-base font-semibold leading-tight text-slate-900 group-hover:text-brand-700">
                {name}
              </h3>
              {contact ? (
                <p className="mt-1 flex items-center gap-1 truncate text-xs text-slate-500">
                  {contactIcon
                    ? (() => {
                        const Icon = contactIcon
                        return <Icon className="h-3 w-3 shrink-0" />
                      })()
                    : null}
                  <span className="truncate">{contact}</span>
                </p>
              ) : (
                <p className="mt-1 text-xs italic text-slate-400">No contact info yet</p>
              )}
            </div>
            <StatusBadge status={lead.status} />
          </div>
        </CardHeader>

        <CardContent className="space-y-3">
          <div>
            <div className="mb-1 flex items-center justify-between gap-2">
              <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                {isPreQualification ? 'Profile complete' : 'Qualification score'}
              </span>
              {lead.status === 'CLOSED' && lead.close_reason ? (
                <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-medium text-slate-700">
                  {CLOSE_REASON_LABEL[lead.close_reason]}
                </span>
              ) : verdict ? (
                <span
                  className={cn(
                    'rounded-full border px-2 py-0.5 text-[10px] font-medium',
                    VERDICT_CHIP[verdict].className
                  )}
                >
                  {VERDICT_CHIP[verdict].label}
                </span>
              ) : null}
            </div>
            <ScoreBar
              value={isPreQualification ? lead.profile_completeness : lead.qualification_score}
            />
          </div>

          <div className="flex items-center justify-between text-xs text-slate-500">
            <span className="flex items-center gap-1">
              <MapPin className="h-3 w-3" />
              {lead.city ?? '—'}
            </span>
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {relativeTime(lead.created_at)}
            </span>
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}
