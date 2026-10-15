import { Loader2, RefreshCw, Shield, Sparkles } from 'lucide-react'
import type { components } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tooltip } from '@/components/ui/tooltip'
import { useGenerateAnalysis, useLatestAnalysis } from '@/api/hooks'
import { GapList } from './GapList'
import { RecommendationCard } from './RecommendationCard'
import { RiskFlagList } from './RiskFlagList'
import { SavingsCard } from './SavingsCard'

type AnalysisOut = components['schemas']['AnalysisOut']

export interface AnalysisPanelProps {
  leadId: string
  /** Seed value from the parent's `LeadDetailOut.latest_analysis`. */
  latestAnalysis: AnalysisOut | null
  /** Why the analysis agent can't run yet (shown as a tooltip), or null if it can. */
  blockedReason: string | null
}

/**
 * Analysis panel embedded in LeadDetailPage. Self-fetches to pick up the
 * most recent analysis independently of the parent's cache.
 */
export function AnalysisPanel({
  leadId,
  latestAnalysis,
  blockedReason,
}: AnalysisPanelProps) {
  const query = useLatestAnalysis(leadId)
  const mutation = useGenerateAnalysis(leadId)
  const analysis: AnalysisOut | null =
    (query.data as AnalysisOut | null | undefined) ?? latestAnalysis
  const isGenerating = mutation.isPending
  const canGenerate = blockedReason === null
  const disabledReason = blockedReason
  const hasAnalysis = analysis !== null && analysis !== undefined

  const generateButton = (
    <Button
      type="button"
      variant={hasAnalysis ? 'outline' : 'default'}
      size="sm"
      onClick={() => mutation.mutate()}
      disabled={!canGenerate || isGenerating}
    >
      {isGenerating ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
      ) : hasAnalysis ? (
        <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
      ) : (
        <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
      )}
      {isGenerating
        ? 'Agent running…'
        : hasAnalysis
          ? 'Re-run analysis agent'
          : 'Run analysis agent'}
    </Button>
  )

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-3 space-y-0">
        <CardTitle className="flex items-center gap-2">
          <Shield className="h-4 w-4 text-brand-600" aria-hidden="true" />
          AI Analysis
        </CardTitle>
        {disabledReason ? (
          <Tooltip side="left" content={disabledReason}>
            <span>{generateButton}</span>
          </Tooltip>
        ) : (
          generateButton
        )}
      </CardHeader>
      <CardContent className="space-y-5">
        {mutation.error ? (
          <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            {mutation.error.message}
          </p>
        ) : null}

        {!hasAnalysis ? (
          <EmptyState blockedReason={blockedReason} onGenerate={() => mutation.mutate()} isGenerating={isGenerating} />
        ) : (
          <>
            {/* Final recommendation sits at the TOP so the broker sees the
                verdict first, then the supporting evidence below. */}
            <RecommendationCard analysis={analysis} />

            <div className="rounded-lg border border-slate-200 bg-slate-50/40 p-4">
              <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Supporting analysis
              </h4>

              <section>
                <h5 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  Coverage gaps
                </h5>
                <GapList gaps={analysis.coverage_gaps ?? []} />
              </section>

              <section className="mt-4">
                <h5 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  Risk flags
                </h5>
                <RiskFlagList flags={analysis.risk_flags ?? []} />
              </section>

              {analysis.potential_savings ? (
                <section className="mt-4">
                  <h5 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                    Potential savings
                  </h5>
                  <SavingsCard savings={analysis.potential_savings} />
                </section>
              ) : null}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}

interface EmptyStateProps {
  blockedReason: string | null
  isGenerating: boolean
  onGenerate: () => void
}

function EmptyState({ blockedReason, isGenerating, onGenerate }: EmptyStateProps) {
  if (blockedReason) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-6 text-center">
        <Sparkles
          className="mx-auto h-6 w-6 text-slate-400"
          aria-hidden="true"
        />
        <p className="mt-2 text-sm font-medium text-slate-700">
          No analysis yet
        </p>
        <p className="mt-1 text-xs text-slate-500">{blockedReason}</p>
      </div>
    )
  }
  return (
    <div className="rounded-lg border border-brand-200 bg-brand-50/50 p-6 text-center">
      <Sparkles
        className="mx-auto h-6 w-6 text-brand-600"
        aria-hidden="true"
      />
      <p className="mt-2 text-sm font-medium text-slate-900">
        Ready to synthesise
      </p>
      <p className="mt-1 text-xs text-slate-600">
        The analysis agent produces a broker-ready analysis: gaps, risks,
        savings, and the recommended next step.
      </p>
      <Button
        type="button"
        className="mt-4"
        size="sm"
        onClick={onGenerate}
        disabled={isGenerating}
      >
        {isGenerating ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
        ) : (
          <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
        )}
        {isGenerating ? 'Agent running…' : 'Run analysis agent'}
      </Button>
    </div>
  )
}
