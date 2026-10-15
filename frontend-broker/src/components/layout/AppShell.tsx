import * as React from 'react'
import { Link, Outlet, useLocation, useSearchParams } from 'react-router-dom'
import { LayoutGrid, PanelLeftClose, PanelLeftOpen, ShieldCheck } from 'lucide-react'
import type { components } from '@/api/types'
import { useLeads } from '@/api/hooks'
import { STATUS_ORDER, statusTabLabel } from '@/components/pipeline/StatusBadge'
import { STAGE_ICON } from '@/components/pipeline/stages'
import { cn } from '@/lib/utils'

type LeadStatus = components['schemas']['LeadStatus']

const COLLAPSED_KEY = 'securelife.sidebar.collapsed'

function readCollapsed(): boolean {
  try {
    return window.localStorage.getItem(COLLAPSED_KEY) === '1'
  } catch {
    return false
  }
}

/**
 * Broker app frame: a floating, collapsible sidebar listing the pipeline
 * stages with live counts, and the page content beside it. Stage links drive
 * the dashboard filter through `?stage=`, so a filtered view is linkable.
 */
export function AppShell() {
  const [collapsed, setCollapsed] = React.useState(readCollapsed)
  const { pathname } = useLocation()
  const [params] = useSearchParams()
  const activeStage = pathname === '/' ? (params.get('stage') ?? 'ALL') : null

  // Same query key as the unfiltered dashboard, so this shares its poll.
  const { data: leads = [] } = useLeads({})
  const counts = React.useMemo(() => {
    const byStage = new Map<LeadStatus, number>()
    for (const lead of leads) byStage.set(lead.status, (byStage.get(lead.status) ?? 0) + 1)
    return byStage
  }, [leads])

  const toggle = () => {
    setCollapsed((c) => {
      try {
        window.localStorage.setItem(COLLAPSED_KEY, c ? '0' : '1')
      } catch {
        // Storage unavailable (private mode): the toggle still works for this visit.
      }
      return !c
    })
  }

  const items = [
    { key: 'ALL', label: 'All prospects', icon: LayoutGrid, to: '/', count: leads.length },
    ...STATUS_ORDER.map((s) => ({
      key: s,
      label: statusTabLabel(s),
      icon: STAGE_ICON[s],
      to: `/?stage=${s}`,
      count: counts.get(s) ?? 0,
    })),
  ]

  return (
    <div className="flex min-h-screen gap-4 p-3 md:p-4">
      <aside
        className={cn(
          'sticky top-3 flex h-[calc(100vh-1.5rem)] shrink-0 flex-col rounded-3xl bg-white p-3 transition-[width] duration-200 md:top-4 md:h-[calc(100vh-2rem)]',
          collapsed ? 'w-[72px]' : 'w-[72px] md:w-64'
        )}
      >
        <Link to="/" className="flex items-center gap-3 rounded-2xl p-1.5">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-ink">
            <ShieldCheck className="h-5 w-5 text-lime" aria-hidden="true" />
          </span>
          <span className={cn('min-w-0 leading-tight', collapsed ? 'hidden' : 'hidden md:block')}>
            <span className="block text-[15px] font-bold tracking-tight text-ink">SecureLife</span>
            <span className="block text-xs font-medium text-muted">Broker workspace</span>
          </span>
        </Link>

        <p
          className={cn(
            'mb-2 mt-7 px-3 text-[11px] font-semibold uppercase tracking-wider text-muted',
            collapsed ? 'hidden' : 'hidden md:block'
          )}
        >
          Pipeline
        </p>
        <nav className={cn('flex flex-col gap-1', collapsed && 'mt-7')} aria-label="Pipeline stages">
          {items.map((item) => {
            const active = activeStage === item.key
            const Icon = item.icon
            return (
              <Link
                key={item.key}
                to={item.to}
                title={item.label}
                aria-current={active ? 'page' : undefined}
                className={cn(
                  'group flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm font-semibold transition-colors',
                  active ? 'bg-ink text-white' : 'text-ink-2 hover:bg-mist'
                )}
              >
                <Icon className={cn('h-[18px] w-[18px] shrink-0', active ? 'text-lime' : 'text-muted')} />
                <span className={cn('min-w-0 flex-1 truncate', collapsed ? 'hidden' : 'hidden md:block')}>
                  {item.label}
                </span>
                <span
                  className={cn(
                    'rounded-full px-2 py-0.5 text-[11px] font-bold tabular-nums',
                    active ? 'bg-lime text-ink' : 'bg-mist text-muted',
                    collapsed ? 'hidden' : 'hidden md:inline'
                  )}
                >
                  {item.count}
                </span>
              </Link>
            )
          })}
        </nav>

        <button
          type="button"
          onClick={toggle}
          className="mt-auto hidden items-center gap-3 rounded-2xl px-3 py-2.5 text-sm font-semibold text-muted hover:bg-mist hover:text-ink md:flex"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? (
            <PanelLeftOpen className="h-[18px] w-[18px] shrink-0" />
          ) : (
            <>
              <PanelLeftClose className="h-[18px] w-[18px] shrink-0" />
              <span>Collapse</span>
            </>
          )}
        </button>
      </aside>

      <main className="min-w-0 flex-1 pb-8">
        <Outlet />
      </main>
    </div>
  )
}
