import * as React from 'react'
import { RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { ChatWindow, type ChatWindowMessage } from '@/components/chat/ChatWindow'
import { ChatInput } from '@/components/chat/ChatInput'
import { DocumentShare } from '@/components/documents/DocumentShare'
import { useStartSession, useLeadDetail, useInvalidateLeadDetail } from '@/api/hooks'
import { openChatStream, type ChatStreamSession } from '@/lib/sse'

const LEAD_STORAGE_KEY = 'securelife.prospect.chatLeadId'

export function ChatPage() {
  const [leadId, setLeadId] = React.useState<string | null>(() => {
    if (typeof window === 'undefined') return null
    return window.localStorage.getItem(LEAD_STORAGE_KEY)
  })

  const startSession = useStartSession()
  const invalidateDetail = useInvalidateLeadDetail()
  const leadDetail = useLeadDetail(leadId)

  const startAttemptedRef = React.useRef(false)
  React.useEffect(() => {
    if (leadId) return
    if (startAttemptedRef.current) return
    if (startSession.isPending) return
    startAttemptedRef.current = true
    startSession.mutate(undefined, {
      onSuccess: (data) => {
        window.localStorage.setItem(LEAD_STORAGE_KEY, data.lead_id)
        setLeadId(data.lead_id)
      },
      onError: () => {
        startAttemptedRef.current = false
      },
    })
  }, [leadId, startSession])

  const [streamingMessage, setStreamingMessage] = React.useState<string>('')
  const [awaitingFirstToken, setAwaitingFirstToken] = React.useState(false)
  const [isStreaming, setIsStreaming] = React.useState(false)
  const [streamError, setStreamError] = React.useState<string | null>(null)
  const [pendingUserMessages, setPendingUserMessages] = React.useState<ChatWindowMessage[]>([])
  const streamRef = React.useRef<ChatStreamSession | null>(null)

  // Drop optimistic user bubbles once the backend echoes them back.
  React.useEffect(() => {
    const detail = leadDetail.data
    if (!detail?.messages || pendingUserMessages.length === 0) return
    const persisted = new Set(
      detail.messages.filter((m) => m.role === 'USER').map((m) => m.content)
    )
    setPendingUserMessages((prev) => prev.filter((m) => !persisted.has(m.content)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [leadDetail.data?.messages])

  const combinedMessages = React.useMemo<ChatWindowMessage[]>(() => {
    const base: ChatWindowMessage[] = []
    const persisted = leadDetail.data?.messages ?? []
    for (const m of persisted) {
      base.push({
        id: m.id,
        role: m.role as ChatWindowMessage['role'],
        content: m.content,
        timestamp: m.created_at,
      })
    }
    for (const m of pendingUserMessages) base.push(m)
    if (isStreaming && streamingMessage.length > 0) {
      base.push({
        id: '__streaming__',
        role: 'ASSISTANT',
        content: streamingMessage,
        streaming: true,
      })
    }
    if (streamError) {
      base.push({
        id: '__err__',
        role: 'ERROR',
        content: streamError,
      })
    }
    return base
  }, [leadDetail.data?.messages, pendingUserMessages, isStreaming, streamingMessage, streamError])

  React.useEffect(() => {
    return () => {
      streamRef.current?.cancel()
    }
  }, [])

  const sendMessage = React.useCallback(
    (text: string) => {
      if (!leadId || isStreaming) return
      const optimistic: ChatWindowMessage = {
        id: `__user_${Date.now()}`,
        role: 'USER',
        content: text,
        timestamp: new Date().toISOString(),
      }
      setPendingUserMessages((prev) => [...prev, optimistic])
      setStreamError(null)
      setStreamingMessage('')
      setAwaitingFirstToken(true)
      setIsStreaming(true)

      streamRef.current?.cancel()
      streamRef.current = openChatStream({
        leadId,
        message: text,
        onToken: (chunk) => {
          setAwaitingFirstToken(false)
          setStreamingMessage((prev) => prev + chunk)
        },
        onDone: () => {
          setIsStreaming(false)
          setAwaitingFirstToken(false)
          setStreamingMessage('')
          // Immediate refetch for the message + current state, then a second
          // one shortly after to pick up the delayed background turn extractor
          // (which runs on the backend after we send `done`).
          invalidateDetail(leadId)
          window.setTimeout(() => invalidateDetail(leadId), 2500)
        },
        onError: (err) => {
          setIsStreaming(false)
          setAwaitingFirstToken(false)
          setStreamingMessage('')
          setStreamError(err)
          invalidateDetail(leadId)
        },
      })
    },
    [leadId, isStreaming, invalidateDetail]
  )

  const stopStreaming = React.useCallback(() => {
    streamRef.current?.cancel()
    setIsStreaming(false)
    setAwaitingFirstToken(false)
    setStreamingMessage('')
    if (leadId) invalidateDetail(leadId)
  }, [leadId, invalidateDetail])

  /**
   * Retry the last-sent message after an error (rate limit, transient 5xx, …).
   * Pulls the most recent optimistic user bubble, drops it, and re-fires
   * sendMessage with the same text so the bubble reappears from scratch.
   */
  const retryLastMessage = React.useCallback(() => {
    if (!leadId || isStreaming) return
    // Last entry in pendingUserMessages is the message that errored out.
    const last = pendingUserMessages[pendingUserMessages.length - 1]
    const text = last?.content
    if (!text) {
      setStreamError(null)
      return
    }
    setPendingUserMessages((prev) => prev.slice(0, -1))
    setStreamError(null)
    // Give React a tick to flush the state before re-sending so the previous
    // optimistic bubble doesn't flash alongside the new one.
    window.setTimeout(() => sendMessage(text), 0)
  }, [leadId, isStreaming, pendingUserMessages, sendMessage])

  const startNewConversation = React.useCallback(() => {
    streamRef.current?.cancel()
    window.localStorage.removeItem(LEAD_STORAGE_KEY)
    setLeadId(null)
    setPendingUserMessages([])
    setStreamingMessage('')
    setStreamError(null)
    setIsStreaming(false)
    setAwaitingFirstToken(false)
    startAttemptedRef.current = false
  }, [])

  const sessionError = startSession.error
  const canSend = !!leadId && !isStreaming

  // Reveal the upload card as soon as the assistant has invited an upload.
  // Scanning assistant messages for the invitation is zero-latency and
  // matches the actual UX trigger ("the assistant asked, so show the
  // uploader"), rather than waiting on the background extractor to record
  // the prospect's consent.
  //
  // The regex matches "upload" close to any policy/document word. The chat
  // agent's prompt uses this phrasing in its wrap-up when the prospect has
  // an existing policy.
  const assistantInvitedUpload = React.useMemo(() => {
    const msgs = leadDetail.data?.messages ?? []
    const UPLOAD_INVITE = /upload[^.]{0,80}?(polic|document|pdf|cover|existing)/i
    return msgs.some(
      (m) => m.role === 'ASSISTANT' && UPLOAD_INVITE.test(m.content),
    )
  }, [leadDetail.data?.messages])

  const hasAnyDocument = (leadDetail.data?.documents?.length ?? 0) > 0
  const shouldShowUpload = assistantInvitedUpload || hasAnyDocument

  return (
    <>
    <Card className="flex min-h-[70vh] flex-1 flex-col overflow-hidden border-slate-200/80 shadow-lg">
      <div className="flex items-center justify-between border-b border-slate-200/80 bg-white px-5 py-3">
        <div>
          <p className="text-sm font-semibold text-slate-900">
            Chat with SecureLife
          </p>
          <p className="text-xs text-slate-500">
            We'll ask a few quick questions and connect you with a broker.
          </p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={startNewConversation}
          className="text-slate-500 hover:text-slate-900"
          title="Start a fresh conversation"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          Restart
        </Button>
      </div>

      {sessionError && (
        <div className="border-b border-red-200 bg-red-50 px-5 py-2 text-xs text-red-700">
          Could not start a session. Please refresh and try again.
        </div>
      )}

      <ChatWindow
        messages={combinedMessages}
        awaitingFirstToken={awaitingFirstToken}
        onRetry={retryLastMessage}
        retrying={isStreaming && !!streamError}
      />

      <div className="border-t border-slate-200/80 bg-white">
        <ChatInput
          onSend={sendMessage}
          onStop={stopStreaming}
          streaming={isStreaming}
          disabled={!canSend && !isStreaming}
        />
      </div>
    </Card>

    {shouldShowUpload && (
      <DocumentShare
        leadId={leadId}
        documents={leadDetail.data?.documents ?? []}
      />
    )}
  </>
  )
}
