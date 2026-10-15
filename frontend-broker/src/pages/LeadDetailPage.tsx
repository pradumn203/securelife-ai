import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, AlertCircle } from 'lucide-react'
import { useLeadDetail } from '@/api/hooks'
import { AnalysisPanel } from '@/components/analysis/AnalysisPanel'
import { DocumentsPanel } from '@/components/documents/DocumentsPanel'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ConversationThread } from '@/components/leads/ConversationThread'
import { LeadDetailLayout } from '@/components/leads/LeadDetailLayout'
import { LeadHeader } from '@/components/leads/LeadHeader'
import { QualificationPanel } from '@/components/leads/QualificationPanel'
import { analysisBlockedReason } from '@/components/leads/pipelineGuide'

function Breadcrumb() {
  return (
    <Link
      to="/"
      className="inline-flex items-center gap-1 text-sm text-brand-700 hover:text-brand-800 hover:underline"
    >
      <ArrowLeft className="h-3.5 w-3.5" />
      All prospects
    </Link>
  )
}

export function LeadDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: lead, isLoading, error } = useLeadDetail(id ?? null)

  if (isLoading) {
    return (
      <div className="mx-auto max-w-6xl space-y-5 p-6 lg:p-8">
        <Breadcrumb />
        <div className="h-32 animate-pulse rounded-xl border border-slate-200 bg-white" />
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          <div className="h-96 animate-pulse rounded-xl border border-slate-200 bg-white lg:col-span-2" />
          <div className="h-96 animate-pulse rounded-xl border border-slate-200 bg-white" />
        </div>
      </div>
    )
  }

  if (error || !lead) {
    return (
      <div className="mx-auto max-w-3xl p-8">
        <Breadcrumb />
        <Card className="mt-4 border-red-200 bg-red-50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-red-800">
              <AlertCircle className="h-4 w-4" />
              Could not load lead
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-red-700">
              {error instanceof Error
                ? error.message
                : 'The backend returned no data for this lead id.'}
            </p>
            <div className="mt-4">
              <Link to="/">
                <Button variant="outline" size="sm">
                  Back to all prospects
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  const documents = lead.documents ?? []
  const latestAnalysis = lead.latest_analysis ?? null
  const leadId = lead.id

  return (
    <LeadDetailLayout
      breadcrumb={<Breadcrumb />}
      header={<LeadHeader lead={lead} />}
      qualification={<QualificationPanel lead={lead} />}
      conversation={
        <ConversationThread
          messages={lead.messages ?? []}
          summary={lead.conversation_summary ?? null}
        />
      }
      documents={<DocumentsPanel leadId={leadId} documents={documents} />}
      analysis={
        <AnalysisPanel
          leadId={leadId}
          latestAnalysis={latestAnalysis}
          blockedReason={analysisBlockedReason(lead)}
        />
      }
    />
  )
}
