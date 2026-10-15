import { ShieldCheck } from 'lucide-react'
import { cn } from '@/lib/utils'

/** The SecureLife mark: a lime shield on a near-black tile. Also the assistant's avatar. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <span className={cn('flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-ink', className)}>
      <ShieldCheck className="h-[18px] w-[18px] text-lime" aria-hidden="true" />
    </span>
  )
}
