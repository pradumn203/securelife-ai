import { MessageSquare } from 'lucide-react'
import type { components } from '@/api/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

type Message = components['schemas']['ChatMessageOut']

export interface ConversationThreadProps {
  messages: Message[]
  summary?: string | null
  className?: string
}

/** Format a timestamp as "HH:MM" in the user's local tz. */
function clock(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
  } catch {
    return iso
  }
}

export function ConversationThread({ messages, summary, className }: ConversationThreadProps) {
  const visible = messages.filter((m) => m.role !== 'SYSTEM')

  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2">
            <MessageSquare className="h-4 w-4 text-brand-600" />
            Conversation
          </CardTitle>
          <span className="text-xs text-slate-500">{visible.length} message{visible.length === 1 ? '' : 's'}</span>
        </div>
        {summary && (
          <p className="mt-2 rounded-md bg-brand-50 px-3 py-2 text-xs leading-relaxed text-brand-700">
            <span className="font-semibold">Summary:</span> {summary}
          </p>
        )}
      </CardHeader>

      <CardContent>
        {visible.length === 0 ? (
          <p className="text-sm italic text-slate-400">No messages yet.</p>
        ) : (
          <ScrollArea className="max-h-[26rem] pr-1">
            <ol className="space-y-3">
              {visible.map((m) => {
                const isUser = m.role === 'USER'
                return (
                  <li
                    key={m.id}
                    className={cn('flex', isUser ? 'justify-end' : 'justify-start')}
                  >
                    <div className={cn('max-w-[85%] space-y-1', isUser ? 'items-end' : 'items-start')}>
                      <div
                        className={cn(
                          'rounded-2xl px-4 py-2 text-sm leading-relaxed shadow-sm',
                          isUser
                            ? 'rounded-br-sm bg-brand-600 text-white'
                            : 'rounded-bl-sm border border-slate-200 bg-white text-slate-800'
                        )}
                      >
                        {m.content}
                      </div>
                      <div
                        className={cn(
                          'text-[10px] uppercase tracking-wide text-slate-400',
                          isUser ? 'text-right' : 'text-left'
                        )}
                      >
                        {isUser ? 'Prospect' : 'Assistant'} · {clock(m.created_at)}
                      </div>
                    </div>
                  </li>
                )
              })}
            </ol>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  )
}
