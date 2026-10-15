import { AlertTriangle, BadgeCheck, CircleHelp, Loader2, MessageSquareQuote, RefreshCw, ShieldCheck, Sparkles, XCircle } from 'lucide-react'
import type { components } from '@/api/types'
import { usePatchLead, useQualifyLead } from '@/api/hooks'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ScoreBar } from '@/components/pipeline/ScoreBar'
import { cn } from '@/lib/utils'
import { INSURANCE_TYPE_LABEL, VALUE_LABEL } from './profileLabels'

type Lead = components['schemas']['LeadDetailOut']
type Qualification = components['schemas']['QualificationOut']
type Verdict = Qualification['verdict']
type ChecklistItem = components['schemas']['ProfileChecklistItem']

export interface QualificationPanelProps {
  lead: Lead
}

/** Once a prospect is analysed or closed, qualification is locked. */
const SEALED_STATUSES = new Set(['ANALYZED', 'CLOSED'])

const VERDICT_META: Record<Verdict, { label: string; variant: 'success' | 'danger' | 'warning' }> = {
  QUALIFIED: { label: 'Qualified', variant: 'success' },
  NOT_QUALIFIED: { label: 'Not qualified', variant: 'danger' },
  NEEDS_MORE_INFO: { label: 'Needs more info', variant: 'warning' },
}

const DIMENSION_LABEL: Record<string, string> = {
  need_clarity: 'Need clarity',
  urgency: 'Urgency',
  budget_fit: 'Budget fit',
  coverage_gap: 'Coverage gap',
  engagement: 'Engagement',
}


/**
 * The broker's qualification workspace for one prospect: the question plan
 * the chat agent worked through, the "Run qualification agent" action, and
 * the latest evidence-backed verdict.
 */
export function QualificationPanel({ lead }: QualificationPanelProps) {
  const qualify = useQualifyLead()
  const patch = usePatchLead(lead.id)
  const latest = lead.latest_qualification ?? null
  const sealed = SEALED_STATUSES.has(lead.status)
  const missing = (qualify.error as { missing?: string[] } | null)?.missing ?? []

  const checklist = lead.profile_checklist ?? []
  const core = checklist.filter((i) => i.group === 'core')
  const details = checklist.filter((i) => i.group === 'details')
  const insuranceType = lead.extracted_fields?.insurance_type ?? null

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-3 space-y-0">
        <CardTitle className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-brand-600" aria-hidden="true" />
          Qualification
        </CardTitle>
        {!sealed && (
          <Button
            type="button"
            size="sm"
            variant={latest ? 'outline' : 'default'}
            onClick={() => qualify.mutate(lead.id)}
            disabled={qualify.isPending}
          >
            {qualify.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
            ) : latest ? (
              <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
            ) : (
              <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
            )}
            {qualify.isPending
              ? 'Agent running…'
              : latest
                ? 'Re-run qualification agent'
                : 'Run qualification agent'}
          </Button>
        )}
      </CardHeader>

      <CardContent className="space-y-5">
        {missing.length > 0 && (
          <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            The agent needs a name, a contact detail and the insurance type first. Still
            missing: <span className="font-medium">{missing.join(', ')}</span>. The chat agent
            will keep asking, or you can add them with Edit.
          </p>
        )}
        {qualify.error && missing.length === 0 && (
          <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            {qualify.error.message}
          </p>
        )}

        <section>
          <div className="mb-2 flex items-center justify-between gap-3">
            <h4 className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Profile captured by the chat agent
              {insuranceType ? ` · ${INSURANCE_TYPE_LABEL[insuranceType] ?? insuranceType}` : ''}
            </h4>
            <span className="text-xs tabular-nums text-slate-500">
              {lead.profile_completeness}% complete
            </span>
          </div>
          <ScoreBar value={lead.profile_completeness} showLabel={false} className="mb-3" />
          <div className="grid grid-cols-1 gap-x-6 gap-y-1.5 sm:grid-cols-2">
            {[...core, ...details].map((item) => (
              <ChecklistRow key={`${item.group}-${item.key}`} item={item} />
            ))}
          </div>
          {!insuranceType && (
            <p className="mt-2 text-xs text-slate-500">
              Insurance-specific questions appear once the prospect says what cover they need.
            </p>
          )}
        </section>

        {latest ? (
          <>
            <QualificationResult qualification={latest} />
            {latest.verdict === 'NOT_QUALIFIED' && lead.status !== 'CLOSED' && (
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50/50 px-4 py-3">
                <p className="text-xs text-red-800">
                  The agent recommends not pursuing this prospect. Closing is your call.
                </p>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={patch.isPending}
                  onClick={() =>
                    patch.mutate({
                      status: 'CLOSED',
                      close_reason: 'DISQUALIFIED',
                      close_note: latest.summary || null,
                    })
                  }
                >
                  {patch.isPending ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                  ) : (
                    <XCircle className="h-3.5 w-3.5" aria-hidden="true" />
                  )}
                  Close as disqualified
                </Button>
              </div>
            )}
            {patch.error && (
              <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                Could not close: {patch.error.message}
              </p>
            )}
          </>
        ) : (
          <p className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-3 text-xs text-slate-500">
            {sealed
              ? 'This prospect was analysed or closed without a qualification agent run.'
              : 'Not run yet. The qualification agent reads the whole conversation and scores the prospect on five dimensions, quoting their own words as evidence.'}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

function ChecklistRow({ item }: { item: ChecklistItem }) {
  const display = item.value ? (VALUE_LABEL[item.key]?.[item.value] ?? item.value) : null
  return (
    <div className="flex min-w-0 items-baseline gap-2 text-xs">
      <span
        className={cn(
          'h-1.5 w-1.5 shrink-0 translate-y-[-1px] rounded-full',
          item.captured ? 'bg-emerald-500' : 'bg-slate-300'
        )}
        aria-hidden="true"
      />
      <span className="shrink-0 text-slate-500">{item.label}</span>
      <span
        className={cn('truncate', item.captured ? 'font-medium text-slate-900' : 'italic text-slate-400')}
        title={display ?? undefined}
      >
        {display ?? 'not yet'}
      </span>
    </div>
  )
}

function QualificationResult({ qualification }: { qualification: Qualification }) {
  const meta = VERDICT_META[qualification.verdict]
  const dimensions = qualification.dimensions ?? []
  const redFlags = qualification.red_flags ?? []
  const dealbreakers = qualification.dealbreakers ?? []
  const followUps = qualification.follow_up_questions ?? []

  return (
    <section className="space-y-4 rounded-lg border border-slate-200 bg-slate-50/40 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Badge variant={meta.variant}>{meta.label}</Badge>
          <span className="text-xs text-slate-500">
            by the qualification agent · {new Date(qualification.created_at).toLocaleString()}
          </span>
        </div>
        <div className="w-40">
          <ScoreBar value={qualification.score} />
        </div>
      </div>

      {qualification.summary ? (
        <p className="text-sm leading-relaxed text-slate-800">{qualification.summary}</p>
      ) : null}

      <ul className="space-y-2.5">
        {dimensions.map((d) => (
          <li key={d.key} className="rounded-md border border-slate-100 bg-white p-3">
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-medium text-slate-900">
                {DIMENSION_LABEL[d.key] ?? d.key}
              </span>
              <ScoreDots score={d.score} />
            </div>
            {d.rationale ? <p className="mt-1 text-xs text-slate-600">{d.rationale}</p> : null}
            {d.evidence_quote ? (
              <p className="mt-1.5 flex items-start gap-1.5 text-xs text-slate-700">
                <MessageSquareQuote className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-600" aria-hidden="true" />
                <span className="italic">“{d.evidence_quote}”</span>
                {d.evidence_verified && (
                  <span
                    className="inline-flex shrink-0 items-center gap-0.5 text-[10px] font-medium text-emerald-700"
                    title="Checked server-side: these are the prospect's own words from the transcript."
                  >
                    <BadgeCheck className="h-3 w-3" aria-hidden="true" />
                    verified
                  </span>
                )}
              </p>
            ) : (
              <p
                className="mt-1.5 text-[11px] italic text-slate-400"
                title="Without a verifiable quote from the prospect, this dimension is capped at 3/5."
              >
                No supporting quote from the prospect — capped at 3/5.
              </p>
            )}
          </li>
        ))}
      </ul>

      {dealbreakers.length > 0 && (
        <div className="rounded-md border border-red-200 bg-red-50/60 p-3">
          <h5 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-red-700">
            Dealbreakers
          </h5>
          <ul className="space-y-1.5">
            {dealbreakers.map((d, i) => (
              <li key={i} className="text-sm text-red-900">
                <span className="font-medium">{d.reason}</span>
                {d.evidence_quote ? (
                  <span className="mt-0.5 flex items-start gap-1.5 text-xs text-red-800">
                    <MessageSquareQuote className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                    <span className="italic">“{d.evidence_quote}”</span>
                    <span
                      className="inline-flex shrink-0 items-center gap-0.5 text-[10px] font-medium text-emerald-700"
                      title="Checked server-side: these are the prospect's own words from the transcript."
                    >
                      <BadgeCheck className="h-3 w-3" aria-hidden="true" />
                      verified
                    </span>
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      )}

      {redFlags.length > 0 && (
        <div>
          <h5 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Red flags
          </h5>
          <ul className="space-y-1">
            {redFlags.map((flag, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-500" aria-hidden="true" />
                {flag}
              </li>
            ))}
          </ul>
        </div>
      )}

      {followUps.length > 0 && (
        <div>
          <h5 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Ask on the first call
          </h5>
          <ul className="space-y-1">
            {followUps.map((q, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                <CircleHelp className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-600" aria-hidden="true" />
                {q}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

function ScoreDots({ score }: { score: number }) {
  return (
    <span className="flex items-center gap-1" aria-label={`${score} out of 5`}>
      {[1, 2, 3, 4, 5].map((n) => (
        <span
          key={n}
          className={cn(
            'h-2 w-2 rounded-full',
            n <= score ? (score >= 4 ? 'bg-emerald-500' : score >= 3 ? 'bg-amber-500' : 'bg-rose-500') : 'bg-slate-200'
          )}
        />
      ))}
    </span>
  )
}
