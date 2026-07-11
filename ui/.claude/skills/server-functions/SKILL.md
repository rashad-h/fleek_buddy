---
name: server-functions
description: Use when adding server-only logic, RPC mutations/queries (createServerFn), API/server routes, or streaming/SSE endpoints in this TanStack Start template.
---

# Server Functions & Server Routes (TanStack Start)

Two ways to run code on the server:

- **Server functions** (`createServerFn`) — typed RPC callable from components and loaders. Use for data access and mutations (see `src/server/items.ts`).
- **Server routes** (`createFileRoute(...).server.handlers`) — raw HTTP handlers returning a `Response`. Use for API endpoints, webhooks, and streaming/SSE (see `src/routes/api/chat.ts`).

## Conventions (this template)

- Import alias `#/*` → `src/*`, **with explicit extensions**: `import { db } from '#/db/index.ts'`.
- `verbatimModuleSyntax` + `noUnusedLocals` on → `import type` for types, no unused imports.
- Validate input with `zod` (already a dependency).
- `createServerFn` is imported from `@tanstack/react-start`; `createFileRoute` from `@tanstack/react-router`.

## Server functions: `createServerFn`

`GET` is the default; use `{ method: 'POST' }` for mutations. Chain `.validator()` (parse/narrow input) then `.handler()`.

```ts
// src/server/items.ts (ground truth)
import { createServerFn } from '@tanstack/react-start'
import { desc, eq } from 'drizzle-orm'
import { z } from 'zod'
import { db } from '#/db/index.ts'
import { items } from '#/db/schema.ts'

// GET (default) — no input
export const listItems = createServerFn().handler(async () => {
  return db.select().from(items).orderBy(desc(items.createdAt))
})

// POST — validated input
const createSchema = z.object({
  title: z.string().min(1),
  description: z.string().optional(),
})

export const createItem = createServerFn({ method: 'POST' })
  .validator((data: unknown) => createSchema.parse(data))
  .handler(async ({ data }) => {
    const [row] = await db.insert(items).values(data).returning()
    return row
  })
```

Key points:

- The validator receives raw client input; type it `unknown` and `parse` it. `data` in the handler is the validator's return type.
- The handler runs **only on the server** — safe for `db`, secrets, `process.env`.

### Calling server functions

Invoke with a single object `{ data }` (omit `data` for no-input fns). Works from client components, loaders, and mutations.

```ts
// no input
await listItems()

// with input
await createItem({ data: { title: 'New' } })
```

From a route loader:

```ts
export const Route = createFileRoute('/items-list')({
  loader: () => listItems(),
})
```

From a component via TanStack Query (as `src/routes/items.tsx` does):

```ts
const { data: items = [] } = useQuery({
  queryKey: ['items'],
  queryFn: () => listItems(),
})

const create = useMutation({
  mutationFn: (v: { title: string; description?: string }) =>
    createItem({ data: v }),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['items'] }),
})
```

## Server (API) routes

Put HTTP endpoints under `src/routes/api/**`. Define handlers on the route's `server.handlers` — each receives `{ request, params }` and returns a `Response`.

```ts
// src/routes/api/hello.ts
import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/api/hello')({
  server: {
    handlers: {
      GET: async ({ request }) => new Response('Hello from ' + request.url),
      POST: async ({ request }) => {
        const body = await request.json()
        return new Response(JSON.stringify({ ok: true, name: body.name }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      },
    },
  },
})
```

Dynamic params work here too: `src/routes/api/users/$id.ts` → `({ params }) => params.id`.

## Streaming / Server-Sent Events

The chat endpoint streams via a POST handler that returns an SSE `Response` (`src/routes/api/chat.ts`):

```ts
// src/routes/api/chat.ts (ground truth)
import { chat, toServerSentEventsResponse } from '@tanstack/ai'
import { createFileRoute } from '@tanstack/react-router'
import { apiKeyEnvVar, getChatAdapter } from '#/server/llm.ts'

export const Route = createFileRoute('/api/chat')({
  server: {
    handlers: {
      POST: async ({ request }) => {
        const keyVar = apiKeyEnvVar()
        if (!process.env[keyVar]) {
          return new Response(
            JSON.stringify({ error: `${keyVar} is not set` }),
            {
              status: 500,
              headers: { 'Content-Type': 'application/json' },
            },
          )
        }
        const { messages } = await request.json()
        const stream = chat({ adapter: getChatAdapter(), messages })
        return toServerSentEventsResponse(stream) // SSE Response
      },
    },
  },
})
```

The client consumes it with `useChat({ connection: fetchServerSentEvents('/api/chat') })` from `@tanstack/ai-react` (see `src/routes/chat.tsx`).

Server **functions** can also stream typed data using an async-generator handler; the client iterates the result with `for await`:

```ts
// server
export const streamMessages = createServerFn().handler(async function* () {
  for (const msg of generateMessages()) {
    yield msg // each chunk stays typed
  }
})

// client
for await (const msg of await streamMessages()) {
  append(msg.content)
}
```
