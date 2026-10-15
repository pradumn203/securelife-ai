/**
 * What the broker should do next for a lead, derived from its pipeline stage
 * and documents. Mirrors `backend/app/services/pipeline.py::PipelineRules`;
 * the backend enforces the same order, this module just explains it.
 */
import type { components } from '@/api/types'

type Lead = components['schemas']['LeadDetailOut']

/** Why "Run analysis agent" is unavailable right now, or null if it can run. */
export function analysisBlockedReason(lead: Lead): string | null {
  if (lead.status === 'NEW') return 'Run the qualification agent first.'
  if (lead.status === 'CLOSED') return 'This prospect is closed. Re-open it (Edit → Status) to run a new analysis.'
  const docs = lead.documents ?? []
  if (!docs.some((d) => d.status === 'EXTRACTED')) {
    return docs.length > 0
      ? 'Run the document extractor agent on at least one document first.'
      : 'Upload a policy document and run the document extractor agent first.'
  }
  return null
}

/** One-line "Next step" guidance for the lead's current stage. */
export function nextStep(lead: Lead): string {
  const docs = lead.documents ?? []
  const extracted = docs.some((d) => d.status === 'EXTRACTED')
  const awaitingExtraction = docs.some((d) => d.status === 'UPLOADED' || d.status === 'FAILED')
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
