import type { components } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

type LeadStatus = components['schemas']['LeadStatus']
type CloseReason = components['schemas']['CloseReason']

type BadgeVariant = 'secondary' | 'brand' | 'success' | 'warning' | 'danger' | 'outline' | 'default'

interface StatusMeta {
  variant: BadgeVariant
  /** Short label for badges. */
  label: string
  /** Plural label for the dashboard tab. */
  tab: string
}

/**
 * The five pipeline stages, in order. Each is one dashboard tab; the backend's
 * `PipelineRules` moves a lead between them as agents run and documents arrive.
 */
const STATUS_META: Record<LeadStatus, StatusMeta> = {
  NEW: { variant: 'secondary', label: 'New lead', tab: 'New leads' },
  IN_PROGRESS: { variant: 'brand', label: 'In progress', tab: 'In progress' },
  DOCS_PENDING: { variant: 'default', label: 'Docs pending review', tab: 'Documents pending review' },
  ANALYZED: { variant: 'success', label: 'Analysis complete', tab: 'Completed analyses' },
  CLOSED: { variant: 'outline', label: 'Closed', tab: 'Closed' },
}

export const CLOSE_REASON_LABEL: Record<CloseReason, string> = {
  DISQUALIFIED: 'Disqualified',
  PURCHASED: 'Purchased',
  OTHER: 'Other',
}

export interface StatusBadgeProps {
  status: LeadStatus
  className?: string
}

/**
 * Canonical lead-stage badge. Shared across the prospect board, the lead
 * header, and the broker-edit dialog so the mapping of stage → colour +
 * label lives in exactly one place. Reuse it rather than re-implementing it.
 */
export function StatusBadge({ status, className }: StatusBadgeProps) {
  const meta = STATUS_META[status] ?? { variant: 'secondary' as BadgeVariant, label: String(status) }
  return (
    <Badge variant={meta.variant} className={cn('whitespace-nowrap', className)}>
      {meta.label}
    </Badge>
  )
}

/** Human-friendly stage label without the badge wrapper. */
export function statusLabel(status: LeadStatus): string {
  return STATUS_META[status]?.label ?? String(status)
}

/** Plural label used for the stage's dashboard tab. */
export function statusTabLabel(status: LeadStatus): string {
  return STATUS_META[status]?.tab ?? String(status)
}

/** Pipeline stages in order — the dashboard tab strip and the Edit dialog's select. */
export const STATUS_ORDER: LeadStatus[] = ['NEW', 'IN_PROGRESS', 'DOCS_PENDING', 'ANALYZED', 'CLOSED']
