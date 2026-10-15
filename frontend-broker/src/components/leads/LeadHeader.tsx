import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import { Mail, Phone, MapPin, Pencil, Trash2, User2 } from 'lucide-react'
import type { components } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Dialog, DialogFooter } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { useDeleteLead, usePatchLead } from '@/api/hooks'
import { ScoreBar } from '@/components/pipeline/ScoreBar'
import { CLOSE_REASON_LABEL, STATUS_ORDER, StatusBadge, statusLabel } from '@/components/pipeline/StatusBadge'
import { PipelineStepper } from './PipelineStepper'
import { INSURANCE_TYPE_LABEL, INTENT_LABEL, TIMELINE_LABEL } from './profileLabels'

type Lead = components['schemas']['LeadDetailOut']
type LeadStatus = components['schemas']['LeadStatus']
type LeadUpdate = components['schemas']['LeadUpdate']
type CloseReason = components['schemas']['CloseReason']

export interface LeadHeaderProps {
  lead: Lead
}

type DraftState = {
  full_name: string
  email: string
  phone: string
  city: string
  status: LeadStatus
  close_reason: CloseReason | ''
  close_note: string
  conversation_summary: string
  insurance_type: string
  intent: string
  timeline: string
}

function toDraft(lead: Lead): DraftState {
  const fields = lead.extracted_fields
  return {
    full_name: lead.full_name ?? '',
    email: lead.email ?? '',
    phone: lead.phone ?? '',
    city: lead.city ?? '',
    status: lead.status,
    close_reason: lead.close_reason ?? '',
    close_note: lead.close_note ?? '',
    conversation_summary: lead.conversation_summary ?? '',
    insurance_type: fields?.insurance_type ?? '',
    intent: fields?.intent ?? '',
    timeline: fields?.timeline ?? '',
  }
}

/** Captured profile facts the broker can correct, rendered as selects. */
const PROFILE_SELECTS: { key: 'insurance_type' | 'intent' | 'timeline'; label: string; options: Record<string, string> }[] = [
  { key: 'insurance_type', label: 'Insurance type', options: INSURANCE_TYPE_LABEL },
  { key: 'intent', label: 'Intent', options: INTENT_LABEL },
  { key: 'timeline', label: 'Timeline', options: TIMELINE_LABEL },
]

const SELECT_CLASS =
  'flex h-9 w-full rounded-md border border-slate-300 bg-white px-3 py-1 text-sm text-slate-900 shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500'

export function LeadHeader({ lead }: LeadHeaderProps) {
  const [open, setOpen] = React.useState(false)
  const [confirmDelete, setConfirmDelete] = React.useState(false)
  const [draft, setDraft] = React.useState<DraftState>(() => toDraft(lead))
  const patch = usePatchLead(lead.id)
  const del = useDeleteLead()
  const navigate = useNavigate()
  const hasQualification = Boolean(lead.latest_qualification)

  const onConfirmDelete = async () => {
    try {
      await del.mutateAsync(lead.id)
      setConfirmDelete(false)
      navigate('/')
    } catch {
      // error state shown below the confirm button
    }
  }

  React.useEffect(() => {
    if (open) setDraft(toDraft(lead))
  }, [open, lead])

  const closing = draft.status === 'CLOSED'
  const closeReasonMissing = closing && draft.close_reason === ''

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (closeReasonMissing) return
    const payload: LeadUpdate = {
      full_name: draft.full_name.trim() || null,
      email: draft.email.trim() || null,
      phone: draft.phone.trim() || null,
      city: draft.city.trim() || null,
      status: draft.status,
      ...(closing
        ? { close_reason: draft.close_reason || null, close_note: draft.close_note.trim() }
        : {}),
      conversation_summary: draft.conversation_summary.trim() || null,
      // Empty string clears the field server-side.
      extracted_fields: {
        insurance_type: draft.insurance_type,
        intent: draft.intent,
        timeline: draft.timeline,
      },
    }
    try {
      await patch.mutateAsync(payload)
      setOpen(false)
    } catch {
      // error state surfaced below the form
    }
  }

  return (
    <section className="flex flex-col gap-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-brand-100 text-brand-700">
            <User2 className="h-6 w-6" />
          </div>
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-xl font-semibold leading-tight text-slate-900">
                {lead.full_name ?? 'Unnamed prospect'}
              </h1>
              <StatusBadge status={lead.status} />
            </div>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
              {lead.email && (
                <span className="flex items-center gap-1">
                  <Mail className="h-3 w-3" />
                  {lead.email}
                </span>
              )}
              {lead.phone && (
                <span className="flex items-center gap-1">
                  <Phone className="h-3 w-3" />
                  {lead.phone}
                </span>
              )}
              {lead.city && (
                <span className="flex items-center gap-1">
                  <MapPin className="h-3 w-3" />
                  {lead.city}
                </span>
              )}
              <span className="text-slate-400">Source: {lead.source}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="w-48">
            <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              {hasQualification ? 'Qualification score' : 'Profile complete'}
            </span>
            <ScoreBar
              value={hasQualification ? lead.qualification_score : lead.profile_completeness}
            />
          </div>
          <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
            <Pencil className="h-3.5 w-3.5" />
            Edit
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setConfirmDelete(true)}
            className="text-red-600 hover:bg-red-50 hover:text-red-700"
            title="Delete this prospect and all their data"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Delete
          </Button>
        </div>
      </div>

      <PipelineStepper lead={lead} />

      {lead.status === 'CLOSED' && (
        <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm">
          <span className="font-semibold text-slate-900">
            Closed{lead.close_reason ? ` — ${CLOSE_REASON_LABEL[lead.close_reason]}` : ''}
          </span>
          {lead.close_note ? <span className="text-slate-600">: {lead.close_note}</span> : null}
        </div>
      )}

      <Dialog
        open={open}
        onOpenChange={setOpen}
        title="Edit lead"
        description="Broker-side changes PATCH straight to the backend."
      >
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="space-y-1 text-xs">
              <span className="font-medium text-slate-700">Full name</span>
              <Input
                value={draft.full_name}
                onChange={(e) => setDraft((d) => ({ ...d, full_name: e.target.value }))}
                placeholder="e.g. Priya Nair"
              />
            </label>
            <label className="space-y-1 text-xs">
              <span className="font-medium text-slate-700">City</span>
              <Input
                value={draft.city}
                onChange={(e) => setDraft((d) => ({ ...d, city: e.target.value }))}
                placeholder="Bengaluru"
              />
            </label>
            <label className="space-y-1 text-xs">
              <span className="font-medium text-slate-700">Email</span>
              <Input
                type="email"
                value={draft.email}
                onChange={(e) => setDraft((d) => ({ ...d, email: e.target.value }))}
              />
            </label>
            <label className="space-y-1 text-xs">
              <span className="font-medium text-slate-700">Phone</span>
              <Input
                type="tel"
                value={draft.phone}
                onChange={(e) => setDraft((d) => ({ ...d, phone: e.target.value }))}
              />
            </label>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {PROFILE_SELECTS.map(({ key, label, options }) => (
              <label key={key} className="space-y-1 text-xs">
                <span className="font-medium text-slate-700">{label}</span>
                <select
                  value={draft[key]}
                  onChange={(e) => setDraft((d) => ({ ...d, [key]: e.target.value }))}
                  className={SELECT_CLASS}
                >
                  <option value="">Not captured</option>
                  {Object.entries(options).map(([value, text]) => (
                    <option key={value} value={value}>
                      {text}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </div>

          <label className="block space-y-1 text-xs">
            <span className="font-medium text-slate-700">Status</span>
            <select
              value={draft.status}
              onChange={(e) =>
                setDraft((d) => ({ ...d, status: e.target.value as LeadStatus }))
              }
              className={SELECT_CLASS}
            >
              {STATUS_ORDER.map((s) => (
                <option key={s} value={s}>
                  {statusLabel(s)}
                </option>
              ))}
            </select>
          </label>

          {closing && (
            <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
              <label className="block space-y-1 text-xs">
                <span className="font-medium text-slate-700">Why is this prospect closed?</span>
                <select
                  value={draft.close_reason}
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, close_reason: e.target.value as CloseReason | '' }))
                  }
                  className={SELECT_CLASS}
                  required
                >
                  <option value="">Choose a reason…</option>
                  {(Object.keys(CLOSE_REASON_LABEL) as CloseReason[]).map((r) => (
                    <option key={r} value={r}>
                      {CLOSE_REASON_LABEL[r]}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block space-y-1 text-xs">
                <span className="font-medium text-slate-700">Reason for closure</span>
                <textarea
                  value={draft.close_note}
                  onChange={(e) => setDraft((d) => ({ ...d, close_note: e.target.value }))}
                  rows={2}
                  className="flex w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                  placeholder="e.g. Bought a ₹1Cr term plan on 2 Oct, or: only wanted guaranteed returns."
                />
              </label>
            </div>
          )}

          <label className="block space-y-1 text-xs">
            <span className="font-medium text-slate-700">Conversation summary</span>
            <textarea
              value={draft.conversation_summary}
              onChange={(e) =>
                setDraft((d) => ({ ...d, conversation_summary: e.target.value }))
              }
              rows={3}
              className="flex w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
              placeholder="Short broker note, visible on the prospect card."
            />
          </label>

          {patch.error && (
            <p className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">
              Could not save: {patch.error.message}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={patch.isPending || closeReasonMissing}>
              {patch.isPending ? 'Saving…' : 'Save changes'}
            </Button>
          </DialogFooter>
        </form>
      </Dialog>

      <Dialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title="Delete this prospect?"
        description={
          `This permanently removes ${lead.full_name ?? 'the prospect'}, their ` +
          `conversation, uploaded documents and any generated analysis. This cannot be undone.`
        }
      >
        {del.error && (
          <p className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">
            Could not delete: {del.error.message}
          </p>
        )}
        <DialogFooter>
          <Button type="button" variant="ghost" onClick={() => setConfirmDelete(false)}>
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={onConfirmDelete}
            disabled={del.isPending}
          >
            {del.isPending ? 'Deleting…' : 'Delete permanently'}
          </Button>
        </DialogFooter>
      </Dialog>
    </section>
  )
}
