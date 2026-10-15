import * as React from 'react'
import { cn } from '@/lib/utils'

/**
 * Simple scrollable region. Not a full custom scrollbar — just a styled
 * overflow container so the conversation thread can scroll independently
 * inside a fixed-height card.
 */
export const ScrollArea = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('relative overflow-y-auto overflow-x-hidden', className)}
      {...props}
    />
  )
)
ScrollArea.displayName = 'ScrollArea'
