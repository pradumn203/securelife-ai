/**
 * What the broker should do next for a lead, derived from its pipeline stage
 * and documents. Mirrors `backend/app/services/pipeline.py::PipelineRules`;
 * the backend enforces the same order, this module just explains it.
 */
import type { components } from '@/api/types'

type Lead = components['schemas']['LeadDetailOut']

/** Why "Run analysis agent" is unavailable right now, or null if it can run. */
export function analysisBlockedReason(lead: Lead): string | null {
  if (lead.status === 'CLOSED') return 'This prospect is closed. Re-open it (Edit → Status) to run a new analysis.'
  if (lead.status === 'NEW' || !lead.qualification_verdict) return 'Run the qualification agent first.'
  if (lead.qualification_verdict === 'NOT_QUALIFIED') {
    return 'The qualification agent marked this prospect Not qualified. Close them as disqualified, or correct their details (Edit) and re-run qualification.'
  }
  const docs = lead.documents ?? []
  if (!docs.some((d) => d.status === 'EXTRACTED')) {
    return docs.length > 0
      ? 'Run the document extractor agent on at least one document first.'
      : 'Upload a policy document and run the document extractor agent first.'
  }
  return null
}

/** A caution shown with the analysis when it can run but the lead isn't fully qualified. */
export function analysisCaution(lead: Lead): string | null {
  if (lead.qualification_verdict === 'NEEDS_MORE_INFO' && lead.status !== 'CLOSED') {
    return 'Qualification said Needs more info. The analysis can run, but confirm the missing details with the prospect before acting on it.'
  }
  return null
}

/** One-line "Next step" guidance for the lead's current stage. */
export function nextStep(lead: Lead): string {
  const docs = lead.documents ?? []
  const extracted = docs.some((d) => d.status === 'EXTRACTED')
  const awaitingExtraction = docs.some((d) => d.status === 'UPLOADED' || d.status === 'FAILED')
  if (lead.qualification_verdict === 'NOT_QUALIFIED' && lead.status !== 'CLOSED') {
    return 'Not qualified: close the prospect as disqualified, or correct their details (Edit) and re-run the qualification agent.'
  }
  switch (lead.status) {
    case 'NEW':
      return docs.length > 0
        ? 'Run the qualification agent — this prospect already shared a document, so it moves straight to Documents pending review.'
        : 'Run the qualification agent to move this prospect to In progress.'
    case 'IN_PROGRESS':
      return 'Upload the prospect’s policy document (or wait for them to share one) to move to Documents pending review.'
    case 'DOCS_PENDING':
      if (awaitingExtraction && !extracted) return 'Run the extractor agent on the uploaded document, then run the analysis agent.'
      return 'Run the analysis agent to move this prospect to Completed analyses.'
    case 'ANALYZED':
      return 'Review the recommendation, then close the prospect from Edit (Purchased, Disqualified, or Other).'
    case 'CLOSED':
      return 'Closed. Change the status in Edit to re-open this prospect.'
    default:
      return ''
  }
}
