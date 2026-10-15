import * as React from 'react'
import { useSearchParams } from 'react-router-dom'
import { ArrowUpRight, Search, X } from 'lucide-react'
import type { components } from '@/api/types'
import { useLeads } from '@/api/hooks'
import { Input } from '@/components/ui/input'
import { LeadTable } from '@/components/pipeline/LeadTable'
import { STATUS_ORDER, statusTabLabel } from '@/components/pipeline/StatusBadge'
import { STAGE_HINT, STAGE_ICON } from '@/components/pipeline/stages'
import { cn } from '@/lib/utils'

type LeadStatus = components['schemas']['LeadStatus']

/**
 * Each stage card has its own surface, after the reference design: the stage
 * that needs the broker most (documents to review) is the dark one.
 */
const CARD_TONE: Record<LeadStatus, { card: string; icon: string; sub: string }> = {
  NEW: { card: 'bg-white text-ink', icon: 'bg-mist text-ink', sub: 'text-muted' },
  IN_PROGRESS: { card: 'bg-lavender text-lavender-ink', icon: 'bg-white/70 text-lavender-ink', sub: 'text-lavender-ink/75' },
  DOCS_PENDING: { card: 'bg-ink text-white', icon: 'bg-lime text-ink', sub: 'text-white/60' },
  ANALYZED: { card: 'bg-lime text-lime-ink', icon: 'bg-white/70 text-lime-ink', sub: 'text-lime-ink/75' },
  CLOSED: { card: 'bg-mist text-ink', icon: 'bg-white text-ink', sub: 'text-muted' },
}

const dateFmt = new Intl.DateTimeFormat('en-IN', { weekday: 'long', day: 'numeric', month: 'long' })

/** Small debounce so typing in the search box doesn't thrash the backend. */
function useDebounced<T>(value: T, delay = 250): T {
  const [debounced, setDebounced] = React.useState(value)
  React.useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), delay)
    return () => window.clearTimeout(id)
  }, [value, delay])
  return debounced
}

function isStage(value: string | null): value is LeadStatus {
  return value !== null && (STATUS_ORDER as string[]).includes(value)
}

export function DashboardPage() {
  const [params, setParams] = useSearchParams()
  const stageParam = params.get('stage')
  const stage: LeadStatus | null = isStage(stageParam) ? stageParam : null
  const [today] = React.useState(() => dateFmt.format(new Date()))
  const [search, setSearch] = React.useState('')
  const debouncedSearch = useDebounced(search, 250)

  // Fetch every stage once and filter client-side, so switching stages is
  // instant and every count stays live from the same 5-second poll.
  const { data: leads = [], isLoading, error } = useLeads({ search: debouncedSearch || null })

  const counts = React.useMemo(() => {
    const byStage = new Map<LeadStatus, number>()
    for (const lead of leads) byStage.set(lead.status, (byStage.get(lead.status) ?? 0) + 1)
    return byStage
  }, [leads])

  const visible = React.useMemo(
    () => (stage ? leads.filter((l) => l.status === stage) : leads),
    [leads, stage]
  )

  const selectStage = (next: LeadStatus) => {
    setParams(stage === next ? {} : { stage: next })
  }

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-4 px-1 pt-2">
        <div>
          <p className="text-sm font-medium text-muted">{today}</p>
          <h1 className="mt-1 text-3xl font-bold tracking-tight text-ink">Pipeline</h1>
        </div>
        <div className="relative w-full sm:w-80">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input
            placeholder="Search name, email or phone"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10 pr-9"
            aria-label="Search prospects"
          />
          {search ? (
            <button
              type="button"
              onClick={() => setSearch('')}
              aria-label="Clear search"
              className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded-full p-1 text-muted hover:bg-mist hover:text-ink"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          ) : null}
        </div>
      </header>

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-5" aria-label="Pipeline stages">
        {STATUS_ORDER.map((s) => {
          const tone = CARD_TONE[s]
          const Icon = STAGE_ICON[s]
          const active = stage === s
          return (
            <button
              key={s}
              type="button"
              onClick={() => selectStage(s)}
              aria-pressed={active}
              className={cn(
                'group flex min-h-[148px] flex-col rounded-3xl p-5 text-left transition-transform hover:-translate-y-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-ink focus-visible:ring-offset-2 focus-visible:ring-offset-canvas',
                tone.card,
                active && 'ring-2 ring-ink ring-offset-2 ring-offset-canvas'
              )}
            >
              <div className="flex items-start justify-between">
                <span className={cn('flex h-9 w-9 items-center justify-center rounded-full', tone.icon)}>
                  <Icon className="h-4 w-4" aria-hidden="true" />
                </span>
                <ArrowUpRight
                  className={cn('h-4 w-4 opacity-50 transition-opacity group-hover:opacity-100', active && 'opacity-100')}
                  aria-hidden="true"
                />
              </div>
              <span className="mt-auto pt-4 text-4xl font-bold leading-none tracking-tight tabular-nums">
                {counts.get(s) ?? 0}
              </span>
              <span className="mt-2 text-sm font-bold leading-tight">{statusTabLabel(s)}</span>
              <span className={cn('mt-0.5 text-xs font-medium leading-snug', tone.sub)}>{STAGE_HINT[s]}</span>
            </button>
          )
        })}
      </section>

      <section className="rounded-3xl bg-white" aria-label="Prospects">
        <div className="flex flex-wrap items-center justify-between gap-2 px-5 pb-1 pt-5">
          <div className="flex items-baseline gap-2">
            <h2 className="text-lg font-bold tracking-tight text-ink">
              {stage ? statusTabLabel(stage) : 'All prospects'}
            </h2>
            <span className="text-sm font-semibold text-muted tabular-nums">{visible.length}</span>
          </div>
          {stage ? (
            <button
              type="button"
              onClick={() => setParams({})}
              className="rounded-full bg-mist px-3 py-1 text-xs font-semibold text-ink-2 hover:bg-line"
            >
              Show all stages
            </button>
          ) : null}
        </div>
        <LeadTable leads={visible} isLoading={isLoading} error={error} />
      </section>
    </div>
  )
}
