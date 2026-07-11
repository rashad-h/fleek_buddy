import type {
  DecisionEvent,
  Item,
  Negotiation,
  NegotiationDetail,
} from '#/lib/types.ts'

const API_BASE = import.meta.env.VITE_API_URL ?? '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`API ${res.status}: ${body || res.statusText}`)
  }
  return res.json() as Promise<T>
}

export function fetchItems(): Promise<Array<Item>> {
  return request<Array<Item>>('/items')
}

export function fetchItem(id: number | string): Promise<Item> {
  return request<Item>(`/items/${id}`)
}

export async function fetchNegotiationForItem(
  itemId: number | string,
  buyerId: string,
): Promise<Negotiation | null> {
  const res = await fetch(
    `${API_BASE}/items/${itemId}/negotiation?buyer_id=${encodeURIComponent(buyerId)}`,
  )
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`)
  return res.json() as Promise<Negotiation>
}

export type CreateNegotiationInput = {
  item_id: number
  buyer_id: string
  offer_price: number
  message?: string
}

export function createNegotiation(
  input: CreateNegotiationInput,
): Promise<Negotiation> {
  return request<Negotiation>('/negotiations', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function fetchNegotiation(
  id: number | string,
): Promise<NegotiationDetail> {
  return request<NegotiationDetail>(`/negotiations/${id}`)
}

export type StreamHandlers = {
  onToken: (text: string) => void
  onDecision: (decision: DecisionEvent) => void
  onError: (detail: string) => void
  onDone: () => void
}

/**
 * POST to an SSE endpoint and dispatch its events. EventSource cannot POST,
 * so frames are parsed off a fetch ReadableStream.
 */
export async function streamAgentReply(
  path: string,
  body: Record<string, unknown>,
  handlers: StreamHandlers,
): Promise<void> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch (err) {
    handlers.onError(err instanceof Error ? err.message : 'Network error')
    handlers.onDone()
    return
  }
  if (!res.ok || !res.body) {
    const detail = await res.text().catch(() => '')
    handlers.onError(detail || `API ${res.status}`)
    handlers.onDone()
    return
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const dispatch = (frame: string) => {
    let event = 'message'
    let data = ''
    for (const line of frame.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim()
      else if (line.startsWith('data:')) data += line.slice(5).trim()
    }
    if (!data) return
    switch (event) {
      case 'token':
        handlers.onToken((JSON.parse(data) as { text: string }).text)
        break
      case 'decision':
        handlers.onDecision(JSON.parse(data) as DecisionEvent)
        break
      case 'error':
        handlers.onError((JSON.parse(data) as { detail: string }).detail)
        break
      case 'done':
        break
    }
  }

  try {
    let streamDone = false
    while (!streamDone) {
      const chunk = await reader.read()
      streamDone = chunk.done
      if (chunk.value === undefined) continue
      buffer += decoder.decode(chunk.value, { stream: true })
      let sep = buffer.indexOf('\n\n')
      while (sep !== -1) {
        dispatch(buffer.slice(0, sep))
        buffer = buffer.slice(sep + 2)
        sep = buffer.indexOf('\n\n')
      }
    }
    if (buffer.trim()) dispatch(buffer)
  } catch (err) {
    handlers.onError(err instanceof Error ? err.message : 'Stream error')
  } finally {
    handlers.onDone()
  }
}
