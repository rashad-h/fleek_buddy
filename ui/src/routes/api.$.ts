import { createFileRoute } from '@tanstack/react-router'

const BACKEND_URL = process.env.BACKEND_URL ?? 'http://localhost:8000'

// Server-side proxy to the FastAPI backend. The Nitro dev server handles
// requests before Vite's `server.proxy`, so /api is forwarded here instead.
// Streams response bodies through untouched, which SSE depends on.
async function proxy({
  request,
  params,
}: {
  request: Request
  params: { _splat?: string }
}): Promise<Response> {
  const url = new URL(request.url)
  const target = `${BACKEND_URL}/api/${params._splat ?? ''}${url.search}`
  const headers = new Headers(request.headers)
  headers.delete('host')
  return fetch(target, {
    method: request.method,
    headers,
    body: request.body,
    // Required by undici when forwarding a streaming request body.
    // @ts-expect-error not yet in the fetch types
    duplex: 'half',
  })
}

export const Route = createFileRoute('/api/$')({
  server: {
    handlers: {
      GET: proxy,
      POST: proxy,
    },
  },
})
