import { Link, NavLink, Outlet } from 'react-router-dom'
import { LayoutDashboard, Shield } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function AppShell() {
  return (
    <div className="min-h-screen">
      <nav className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <Link
            to="/"
            className="flex items-center gap-2 font-semibold text-slate-900 hover:text-brand-700"
          >
            <Shield className="h-5 w-5 text-brand-600" />
            <span>SecureLife AI</span>
            <span className="hidden rounded-full bg-brand-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-brand-700 sm:inline">
              Broker
            </span>
          </Link>
          <div className="flex items-center gap-1">
            <NavLink to="/" end>
              {({ isActive }) => (
                <Button
                  variant={isActive ? 'secondary' : 'ghost'}
                  size="sm"
                  className={cn(isActive && 'text-slate-900')}
                >
                  <LayoutDashboard className="h-4 w-4" />
                  Prospects
                </Button>
              )}
            </NavLink>
          </div>
        </div>
      </nav>
      <main className="pb-12">
        <Outlet />
      </main>
    </div>
  )
}
