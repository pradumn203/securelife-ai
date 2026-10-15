import { Shield } from 'lucide-react'
import type { ReactNode } from 'react'

/**
 * Prospect-facing chrome. Deliberately minimal — no broker nav, no CRM
 * language, no "pipeline" links. Just a brand mark and a chat.
 */
export function ProspectShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-slate-200/70 bg-white/70 backdrop-blur">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3 sm:px-6">
          <div className="flex items-center gap-2 font-semibold text-slate-900">
            <Shield className="h-5 w-5 text-brand-600" />
            <span>SecureLife</span>
          </div>
          <span className="text-xs text-slate-500">
            Insurance brokers · India
          </span>
        </div>
      </header>
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 py-6 sm:px-6">
        {children}
      </main>
      <footer className="pb-6 pt-2 text-center text-[11px] text-slate-400">
        Your details are shared only with a SecureLife broker. No marketing lists.
      </footer>
    </div>
  )
}
