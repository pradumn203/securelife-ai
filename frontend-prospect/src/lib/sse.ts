/**
 * Server-Sent Events helper for the chat stream endpoint.
 *
 * `EventSource` is GET-only. Our `/api/chat/stream` endpoint is POST (the body
 * carries `lead_id` + `message`), so we use `fetch()` with a `ReadableStream`
 * and parse SSE frames by hand. Frames look like:
 *
 *     data: {"type":"token","text":"..."}\n\n
 *     data: {"type":"done","message_id":"...","qualification_score":42,"status":"QUALIFIED"}\n\n
 *     data: {"type":"error","error":"..."}\n\n
 */

/** Same base as the REST client: empty in dev (Vite proxies /api), the backend origin in prod. */
const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''

export type ChatStreamEvent =
  | { type: 'token'; text: string }
  | {
      type: 'done'
      message_id: string
      qualification_score: number
      status: string
    }
  | { type: 'error'; error: string }

export interface OpenChatStreamParams {
  leadId: string
  message: string
  onToken: (text: string) => void
  onDone: (payload: {
    message_id: string
    qualification_score: number
    status: string
  }) => void
  onError: (error: string) => void
  /** Called when the stream closes for any reason (success, error, abort). */
  onClose?: () => void
  /** Milliseconds without a token before the stream is aborted. Default 60s. */
  idleTimeoutMs?: number
}

/**
 * Starts a chat-stream request. Returns a `ChatStreamSession` that exposes
 * `.cancel()` so the caller can tear the stream down (e.g. on unmount or when
 * the user navigates away).
 */
export class ChatStreamSession {
  private readonly controller: AbortController
  private closed = false

  constructor(controller: AbortController) {
    this.controller = controller
  }

  /** Abort the underlying fetch. Safe to call multiple times. */
  cancel(): void {
    if (this.closed) return
    this.closed = true
    try {
      this.controller.abort()
    } catch {
      // ignore — already aborted
    }
  }

  get isClosed(): boolean {
    return this.closed
  }
}

export function openChatStream(params: OpenChatStreamParams): ChatStreamSession {
  const {
    leadId,
    message,
    onToken,
    onDone,
    onError,
    onClose,
    idleTimeoutMs = 60_000,
  } = params

  const controller = new AbortController()
  const session = new ChatStreamSession(controller)

  let idleTimer: ReturnType<typeof setTimeout> | null = null
  const resetIdleTimer = () => {
    if (idleTimer) clearTimeout(idleTimer)
    idleTimer = setTimeout(() => {
      onError(`No tokens received for ${Math.round(idleTimeoutMs / 1000)}s — aborting.`)
      session.cancel()
    }, idleTimeoutMs)
  }

  const close = () => {
    if (idleTimer) {
      clearTimeout(idleTimer)
      idleTimer = null
    }
    onClose?.()
  }

  const run = async () => {
    let finished = false
    try {
      const res = await fetch(`${API_BASE}/api/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        },
        body: JSON.stringify({ lead_id: leadId, message }),
        signal: controller.signal,
      })

      if (!res.ok || !res.body) {
        const detail = await safeReadText(res)
        onError(`Chat stream failed (HTTP ${res.status}): ${detail || 'no body'}`)
        return
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      resetIdleTimer()

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        // SSE frames are separated by a blank line (\n\n). A frame may contain
        // multiple `data:` lines but the backend here emits exactly one.
        const frames = buffer.split('\n\n')
        buffer = frames.pop() ?? ''

        for (const frame of frames) {
          const dataLine = extractData(frame)
          if (!dataLine) continue
          let event: ChatStreamEvent
          try {
            event = JSON.parse(dataLine) as ChatStreamEvent
          } catch {
            // ignore malformed frames instead of blowing up the stream
            continue
          }
          resetIdleTimer()

          if (event.type === 'token') {
            onToken(event.text)
          } else if (event.type === 'done') {
            finished = true
            onDone({
              message_id: event.message_id,
              qualification_score: event.qualification_score,
              status: event.status,
            })
          } else if (event.type === 'error') {
            finished = true
            onError(event.error)
          }
        }
      }

      // Flush any trailing frame left in the buffer.
      if (!finished && buffer.trim().length > 0) {
        const dataLine = extractData(buffer)
        if (dataLine) {
          try {
            const event = JSON.parse(dataLine) as ChatStreamEvent
            if (event.type === 'token') onToken(event.text)
            else if (event.type === 'done')
              onDone({
                message_id: event.message_id,
                qualification_score: event.qualification_score,
                status: event.status,
              })
            else if (event.type === 'error') onError(event.error)
          } catch {
            // swallow
          }
        }
      }
    } catch (err) {
      if (controller.signal.aborted) {
        // User- or timeout-initiated abort — no error surfacing needed unless
        // we never got a `done` frame. Caller already knows via `onError` in
        // the timeout case.
      } else {
        onError(err instanceof Error ? err.message : String(err))
      }
    } finally {
      close()
    }
  }

  void run()
  return session
}

function extractData(frame: string): string | null {
  // A frame can have multiple lines (e.g. `event:`, `id:`, `data:`). We only
  // care about data lines; join them if there are several.
  const lines = frame.split('\n')
  const dataParts: string[] = []
  for (const raw of lines) {
    const line = raw.replace(/\r$/, '')
    if (line.startsWith('data:')) {
      dataParts.push(line.slice(5).trimStart())
    }
  }
  if (dataParts.length === 0) return null
  return dataParts.join('\n')
}

async function safeReadText(res: Response): Promise<string> {
  try {
    return await res.text()
  } catch {
    return ''
  }
}
