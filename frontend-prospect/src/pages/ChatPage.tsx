import * as React from 'react'
import { SquarePen } from 'lucide-react'
import { BrandMark } from '@/components/layout/BrandMark'
import { ChatWindow, type ChatWindowMessage } from '@/components/chat/ChatWindow'
import { ChatInput } from '@/components/chat/ChatInput'
import { AttachButton, DocumentChips } from '@/components/documents/DocumentShare'
import { useDocumentShare } from '@/components/documents/useDocumentShare'
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

  const documents = leadDetail.data?.documents ?? []
  const shouldShowUpload = assistantInvitedUpload || documents.length > 0
  const share = useDocumentShare(leadId, documents)

  return (
    <>
      <header className="flex shrink-0 items-center justify-between px-4 py-3 sm:px-6">
        <div className="flex items-center gap-2.5">
          <BrandMark />
          <div className="leading-tight">
            <p className="text-[15px] font-bold tracking-tight text-ink">SecureLife</p>
            <p className="text-xs font-medium text-muted">Insurance brokers · India</p>
          </div>
        </div>
        <button
          type="button"
          onClick={startNewConversation}
          title="Start a fresh conversation"
          className="inline-flex h-9 items-center gap-2 rounded-full px-3.5 text-sm font-semibold text-ink-2 hover:bg-mist"
        >
          <SquarePen className="h-4 w-4" aria-hidden="true" />
          New chat
        </button>
      </header>

      {sessionError ? (
        <div className="mx-auto mt-2 w-full max-w-3xl px-4 sm:px-6">
          <p className="rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-700">
            We couldn't start your chat. Please refresh the page and try again.
          </p>
        </div>
      ) : null}

      <ChatWindow
        className="min-h-0"
        messages={combinedMessages}
        awaitingFirstToken={awaitingFirstToken}
        onRetry={retryLastMessage}
        retrying={isStreaming && !!streamError}
      />

      <div className="shrink-0 px-3 pb-3 sm:px-6">
        <div className="mx-auto w-full max-w-3xl">
          <ChatInput
            onSend={sendMessage}
            onStop={stopStreaming}
            streaming={isStreaming}
            disabled={!canSend && !isStreaming}
            placeholder={leadId ? 'Message SecureLife' : 'Starting your chat…'}
            attachments={shouldShowUpload ? <DocumentChips share={share} documents={documents} /> : null}
            tools={shouldShowUpload ? <AttachButton share={share} highlight={documents.length === 0} /> : null}
            onDropFile={shouldShowUpload ? (file) => void share.upload(file) : undefined}
          />
          <p className="mt-2 text-center text-[11px] font-medium text-muted">
            Your details are shared only with a SecureLife broker. No marketing lists.
          </p>
        </div>
      </div>
    </>
  )
}
