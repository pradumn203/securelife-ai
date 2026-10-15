/**
 * Per-stage presentation shared by the sidebar and the dashboard's stage
 * cards: an icon and a one-line description of what the broker does next.
 */
import { Archive, ClipboardCheck, FileText, Inbox, Loader, type LucideIcon } from 'lucide-react'
import type { components } from '@/api/types'

type LeadStatus = components['schemas']['LeadStatus']

export const STAGE_ICON: Record<LeadStatus, LucideIcon> = {
  NEW: Inbox,
  IN_PROGRESS: Loader,
  DOCS_PENDING: FileText,
  ANALYZED: ClipboardCheck,
  CLOSED: Archive,
}

export const STAGE_HINT: Record<LeadStatus, string> = {
  NEW: 'Waiting for the qualification agent',
  IN_PROGRESS: 'Qualified, waiting for a policy',
  DOCS_PENDING: 'Ready for extraction and analysis',
  ANALYZED: 'Analysis ready, close the deal',
  CLOSED: 'Purchased, disqualified or other',
}
