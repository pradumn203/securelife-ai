import type { ReactNode } from 'react'

/**
 * Full-height frame for the chat. Deliberately minimal: no broker nav, no CRM
 * language. The chat page renders its own top bar and composer inside it.
 */
export function ProspectShell({ children }: { children: ReactNode }) {
  return <div className="flex h-dvh flex-col">{children}</div>
}
