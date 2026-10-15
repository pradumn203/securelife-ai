import * as React from 'react'
import { Search, X } from 'lucide-react'
import type { components } from '@/api/types'
import { useLeads } from '@/api/hooks'
import { Input } from '@/components/ui/input'
import { Tabs } from '@/components/ui/tabs'
import { PipelineBoard } from '@/components/pipeline/PipelineBoard'
import { STATUS_ORDER, statusTabLabel } from '@/components/pipeline/StatusBadge'

type LeadStatus = components['schemas']['LeadStatus']

type TabValue = 'ALL' | LeadStatus

interface TabConfig {
  value: TabValue
  label: string
  /** Stage this tab shows. `null` → every stage (All). */
  status: LeadStatus | null
}

/** "All" plus one tab per pipeline stage, in pipeline order. */
const TAB_CONFIGS: TabConfig[] = [
  { value: 'ALL', label: 'All', status: null },
  ...STATUS_ORDER.map((s) => ({ value: s, label: statusTabLabel(s), status: s })),
]

/** Small debounce so typing in the search box doesn't thrash the backend. */
function useDebounced<T>(value: T, delay = 250): T {
  const [debounced, setDebounced] = React.useState(value)
  React.useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), delay)
    return () => window.clearTimeout(id)
  }, [value, delay])
  return debounced
}

export function DashboardPage() {
  const [tab, setTab] = React.useState<TabValue>('ALL')
  const [search, setSearch] = React.useState('')
  const debouncedSearch = useDebounced(search, 250)

  // Fetch every stage once and filter client-side, so switching tabs is instant
  // and every tab's count stays live from the same 5-second poll.
  const { data: leads = [], isLoading, error } = useLeads({
    search: debouncedSearch || null,
  })

  // Counts for the tab strip reflect the current search but ignore the active tab.
  const counts = React.useMemo(() => {
    const buckets = new Map<TabValue, number>()
    buckets.set('ALL', leads.length)
    for (const cfg of TAB_CONFIGS) {
      if (cfg.status === null) continue
      const n = leads.filter((l) => l.status === cfg.status).length
      buckets.set(cfg.value, n)
    }
    return buckets
  }, [leads])

  const filtered = React.useMemo(() => {
    const active = TAB_CONFIGS.find((c) => c.value === tab)
    if (!active || active.status === null) return leads
    return leads.filter((l) => l.status === active.status)
  }, [leads, tab])

  const tabOptions = TAB_CONFIGS.map((c) => ({
    value: c.value,
    label: c.label,
    count: counts.get(c.value) ?? 0,
  }))

  return (
    <div className="mx-auto max-w-6xl p-6 lg:p-8">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-900">Prospects</h1>
        <p className="mt-1 text-sm text-slate-500">
          Live view of prospects captured by the SecureLife chat agent.
          Prospects without a name and contact detail are hidden until they share them.
        </p>
      </header>

      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <Tabs<TabValue> value={tab} onValueChange={setTab} options={tabOptions} />
        <div className="relative w-full sm:w-72">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input
            placeholder="Search name, email, phone…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8 pr-8"
            aria-label="Search leads"
          />
          {search && (
            <button
              type="button"
              onClick={() => setSearch('')}
              aria-label="Clear search"
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      <PipelineBoard leads={filtered} isLoading={isLoading} error={error} />
    </div>
  )
}
