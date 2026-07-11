import type {
  MerchantErrorEvent,
  MerchantFramesReadyEvent,
  MerchantItemAnalyzedEvent,
  MerchantJob,
  MerchantJobCreateResponse,
  MerchantStatusEvent,
  MerchantStreamHandlers,
  MerchantSummaryReadyEvent,
} from '#/lib/merchant-types.ts'

const API_BASE = import.meta.env.VITE_API_URL ?? '/api'

export function merchantImageUrl(path: string): string {
  if (path.startsWith('http')) return path
  const base = API_BASE.replace(/\/api$/, '')
  return `${base}${path}`
}

export async function createMerchantJob(
  video: File,
  expectedCount: number,
): Promise<MerchantJobCreateResponse> {
  const form = new FormData()
  form.append('video', video)
  form.append('expected_count', String(expectedCount))
  const res = await fetch(`${API_BASE}/merchant/jobs`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(body || `Upload failed (${res.status})`)
  }
  return res.json() as Promise<MerchantJobCreateResponse>
}

export async function createSampleMerchantJob(
  expectedCount: number,
): Promise<MerchantJobCreateResponse> {
  const form = new FormData()
  form.append('expected_count', String(expectedCount))
  const res = await fetch(`${API_BASE}/merchant/jobs/sample`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(body || `Sample job failed (${res.status})`)
  }
  return res.json() as Promise<MerchantJobCreateResponse>
}

export async function publishMerchantJob(
  jobId: string,
): Promise<{ job_id: string; item_ids: Array<number>; count: number }> {
  const res = await fetch(`${API_BASE}/merchant/jobs/${jobId}/publish`, {
    method: 'POST',
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(body || `Publish failed (${res.status})`)
  }
  return res.json() as Promise<{
    job_id: string
    item_ids: Array<number>
    count: number
  }>
}

export async function fetchMerchantJob(jobId: string): Promise<MerchantJob> {
  const res = await fetch(`${API_BASE}/merchant/jobs/${jobId}`)
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(body || `Job fetch failed (${res.status})`)
  }
  return res.json() as Promise<MerchantJob>
}

export async function streamMerchantJob(
  jobId: string,
  handlers: MerchantStreamHandlers,
): Promise<void> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}/merchant/jobs/${jobId}/events`)
  } catch (err) {
    handlers.onError(err instanceof Error ? err.message : 'Network error')
    handlers.onDone()
    return
  }

  if (!res.ok || !res.body) {
    const detail = await res.text().catch(() => '')
    handlers.onError(detail || `Stream failed (${res.status})`)
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
      case 'status':
        handlers.onStatus(JSON.parse(data) as MerchantStatusEvent)
        break
      case 'frames_ready':
        handlers.onFramesReady(JSON.parse(data) as MerchantFramesReadyEvent)
        break
      case 'item_analyzed':
        handlers.onItemAnalyzed(JSON.parse(data) as MerchantItemAnalyzedEvent)
        break
      case 'summary_ready':
        handlers.onSummaryReady(JSON.parse(data) as MerchantSummaryReadyEvent)
        break
      case 'error':
        handlers.onError((JSON.parse(data) as MerchantErrorEvent).detail)
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
