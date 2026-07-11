---
name: llm
description: Stream LLM chat with TanStack AI (@tanstack/ai) in a TanStack Start route, swap providers (Anthropic/OpenAI) via env, and add tools or structured output.
---

# LLM (TanStack AI, provider-agnostic)

Use when building chat, streaming completions, tool/function calling, or
structured output. This template uses **TanStack AI** (`@tanstack/ai`), not the
Vercel AI SDK. The provider and model are chosen from env, so swapping providers
never touches app code.

## Layout

- `src/server/llm.ts` — provider/model selection from env (the adapter factory)
- `src/routes/api/chat.ts` — SSE streaming chat endpoint
- `src/routes/chat.tsx` — client chat UI using `useChat`

Default model is `claude-sonnet-5` (also valid: `claude-opus-4-8`).

## Provider selection (`src/server/llm.ts`)

The adapter is picked from `LLM_PROVIDER` / `LLM_MODEL`. Adapters come from
`@tanstack/ai-anthropic` / `@tanstack/ai-openai`. Each adapter factory accepts a
typed model union, so the plain string from env is cast:

```ts
import { anthropicText } from '@tanstack/ai-anthropic'
import { openaiText } from '@tanstack/ai-openai'

const DEFAULTS = { provider: 'anthropic', model: 'claude-sonnet-5' }

export function apiKeyEnvVar() {
  const provider = process.env.LLM_PROVIDER ?? DEFAULTS.provider
  return provider === 'openai' ? 'OPENAI_API_KEY' : 'ANTHROPIC_API_KEY'
}

export function getChatAdapter() {
  const provider = process.env.LLM_PROVIDER ?? DEFAULTS.provider
  const model = process.env.LLM_MODEL ?? DEFAULTS.model

  switch (provider) {
    // Adapters take a typed model union; env is a plain string, so cast it.
    case 'anthropic':
      return anthropicText(model as Parameters<typeof anthropicText>[0])
    case 'openai':
      return openaiText(model as Parameters<typeof openaiText>[0])
    default:
      throw new Error(`Unsupported LLM_PROVIDER: ${provider}`)
  }
}
```

Adapters read the API key from the matching env var (`ANTHROPIC_API_KEY` /
`OPENAI_API_KEY`). Extra providers `@tanstack/ai-gemini` and `@tanstack/ai-ollama`
are installed and can be wired into the same `switch`.

### Swapping providers via `.env`

```bash
# Anthropic (default)
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-5      # or claude-opus-4-8
ANTHROPIC_API_KEY=sk-ant-...

# OpenAI
LLM_PROVIDER=openai
LLM_MODEL=gpt-4.1
OPENAI_API_KEY=sk-...
```

No app-code change required — restart to pick up the new env.

## Server route (`src/routes/api/chat.ts`)

The route is a file-route with a POST `server` handler. It builds the adapter,
calls `chat({ adapter, messages })`, and returns the stream via
`toServerSentEventsResponse`.

```ts
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
        return toServerSentEventsResponse(stream)
      },
    },
  },
})
```

## Client hook (`src/routes/chat.tsx`)

`useChat` from `@tanstack/ai-react` drives the UI. `connection` uses
`fetchServerSentEvents('/api/chat')` to consume the SSE stream. Messages carry a
`parts` array; render the ones with `type: 'text'` (other types include
`thinking` and tool calls).

```tsx
import { fetchServerSentEvents, useChat } from '@tanstack/ai-react'
import { useState } from 'react'

function ChatPage() {
  const [input, setInput] = useState('')
  const { messages, sendMessage, isLoading } = useChat({
    connection: fetchServerSentEvents('/api/chat'),
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!input.trim() || isLoading) return
    sendMessage(input) // sendMessage takes the raw string
    setInput('')
  }

  return (
    <form onSubmit={handleSubmit}>
      {messages.map((message) => (
        <div key={message.id}>
          <b>{message.role === 'assistant' ? 'Assistant' : 'You'}</b>
          {message.parts.map((part, i) =>
            part.type === 'text' ? <span key={i}>{part.content}</span> : null,
          )}
        </div>
      ))}
      {/* input + submit button ... */}
    </form>
  )
}
```

`useChat` also returns `error`, `stop`, `reload`, `setMessages`, `clear`.

## Tools / function calling

Define tools with `toolDefinition` from `@tanstack/ai` (input/output validated
with Zod). Attach a `.server(...)` implementation and pass instances via `tools`
to `chat`; the model calls them autonomously and the result is fed back.

```ts
import { chat, toolDefinition } from '@tanstack/ai'
import { z } from 'zod'
import { getChatAdapter } from '#/server/llm.ts'

const getWeather = toolDefinition({
  name: 'get_weather',
  description: 'Get the current weather for a city',
  inputSchema: z.object({ city: z.string() }),
}).server(async ({ city }) => {
  return { temperature: 72, condition: 'Sunny', city }
})

const stream = chat({
  adapter: getChatAdapter(),
  messages,
  tools: [getWeather],
})
```

Client-side tools use `.client(...)` instead and are passed to `useChat({ tools })`;
they execute automatically (no `onToolCall` callback needed).

## Structured output

Pass an `outputSchema` (Zod) to `chat` to get a validated object back. `await`
the call instead of streaming it. Can be combined with `tools` — the model runs
the tool loop, then emits the final structured object.

```ts
import { chat } from '@tanstack/ai'
import { z } from 'zod'

const result = await chat({
  adapter: getChatAdapter(),
  messages: [{ role: 'user', content: 'Recommend a product for a developer' }],
  outputSchema: z.object({ productName: z.string(), reason: z.string() }),
})
// result.productName / result.reason are typed
```
