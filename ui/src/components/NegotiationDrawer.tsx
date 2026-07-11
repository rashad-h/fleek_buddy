import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { acceptCounter, fetchNegotiation, streamAgentReply } from '#/lib/api.ts'
import { formatGBP } from '#/lib/format.ts'
import {
  describeSelection,
  gradesFromCondition,
  toSelection,
} from '#/lib/selection.ts'
import { cn } from '#/lib/utils.ts'
import { Button } from '#/components/ui/button.tsx'
import { GradePicker } from '#/components/GradePicker.tsx'
import { Input } from '#/components/ui/input.tsx'
import { Textarea } from '#/components/ui/textarea.tsx'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '#/components/ui/sheet.tsx'

import type { Item, Message, NegotiationStatus } from '#/lib/types.ts'

type LocalMessage = Pick<
  Message,
  'role' | 'content' | 'offer_amount' | 'offer_selection' | 'action'
>

type NegotiationDrawerProps = {
  item: Item
  negotiationId: number
  autoRespond: boolean
  open: boolean
  onOpenChange: (open: boolean) => void
  onMakeNewOffer: () => void
}

const statusStyles: Record<NegotiationStatus, string> = {
  open: 'bg-muted text-foreground',
  accepted: 'bg-accent text-accent-foreground',
  rejected: 'bg-sale/15 text-sale',
}

export function NegotiationDrawer({
  item,
  negotiationId,
  autoRespond,
  open,
  onOpenChange,
  onMakeNewOffer,
}: NegotiationDrawerProps) {
  const queryClient = useQueryClient()
  const [pendingMessages, setPendingMessages] = useState<Array<LocalMessage>>(
    [],
  )
  const [streamingText, setStreamingText] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamError, setStreamError] = useState('')
  const [draft, setDraft] = useState('')
  const [draftOffer, setDraftOffer] = useState('')
  const [editScope, setEditScope] = useState(false)
  const [quantities, setQuantities] = useState<Record<string, number>>({})
  const autoRespondStarted = useRef(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  const grades = gradesFromCondition(item.condition)

  const { data: negotiation } = useQuery({
    queryKey: ['negotiation', negotiationId],
    queryFn: () => fetchNegotiation(negotiationId),
    enabled: open,
  })

  const status: NegotiationStatus = negotiation?.status ?? 'open'
  const messages = negotiation?.messages ?? []

  const lastCounter = [...messages]
    .reverse()
    .find(
      (m) =>
        m.role === 'agent' && m.action === 'counter' && m.offer_amount != null,
    )

  const invalidate = () => {
    void queryClient.invalidateQueries({
      queryKey: ['negotiation', negotiationId],
    })
    void queryClient.invalidateQueries({
      queryKey: ['negotiation', 'item', String(item.id)],
    })
  }

  const accept = useMutation({
    mutationFn: () => acceptCounter(negotiationId),
    onSuccess: invalidate,
  })

  const finishStream = () => {
    void queryClient
      .invalidateQueries({ queryKey: ['negotiation', negotiationId] })
      .then(() => {
        setPendingMessages([])
        setStreamingText('')
      })
    void queryClient.invalidateQueries({
      queryKey: ['negotiation', 'item', String(item.id)],
    })
    setIsStreaming(false)
  }

  const runStream = (path: string, body: Record<string, unknown>) => {
    setIsStreaming(true)
    setStreamError('')
    setStreamingText('')
    void streamAgentReply(path, body, {
      onToken: (text) => setStreamingText((prev) => prev + text),
      onDecision: () => {},
      onError: (detail) => setStreamError(detail),
      onDone: finishStream,
    })
  }

  useEffect(() => {
    if (open && autoRespond && !autoRespondStarted.current) {
      autoRespondStarted.current = true
      runStream(`/negotiations/${negotiationId}/respond`, {})
    }
    if (!open) autoRespondStarted.current = false
  }, [open, autoRespond, negotiationId])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
  }, [messages.length, pendingMessages.length, streamingText])

  const send = () => {
    const content = draft.trim()
    const offer = draftOffer.trim() === '' ? null : Number(draftOffer)
    if (!content && offer == null) return
    const selection = offer != null && editScope ? toSelection(quantities) : []
    setPendingMessages((prev) => [
      ...prev,
      {
        role: 'buyer',
        content,
        offer_amount: offer,
        offer_selection: selection.length > 0 ? selection : null,
        action: offer != null ? 'offer' : null,
      },
    ])
    setDraft('')
    setDraftOffer('')
    setEditScope(false)
    setQuantities({})
    runStream(`/negotiations/${negotiationId}/messages`, {
      content,
      ...(offer != null ? { offer_amount: offer } : {}),
      ...(offer != null && selection.length > 0 ? { selection } : {}),
    })
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full gap-0 p-0 sm:max-w-[540px]">
        <SheetHeader className="border-b">
          <div className="flex items-center gap-3 pr-8">
            <img
              src={item.image_url}
              alt=""
              className="size-10 rounded-md object-cover"
            />
            <div className="min-w-0 flex-1">
              <SheetTitle className="truncate">{item.title}</SheetTitle>
              <SheetDescription>
                Asking {formatGBP(item.bundle_price)} · {item.vendor_name}
              </SheetDescription>
            </div>
            <span
              className={cn(
                'rounded-md px-2 py-0.5 text-xs font-bold capitalize',
                statusStyles[status],
              )}
            >
              {status}
            </span>
          </div>
        </SheetHeader>

        <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-4">
          {[...messages, ...pendingMessages].map((message, i) => (
            <MessageBubble key={i} message={message} />
          ))}
          {streamingText && (
            <MessageBubble
              message={{
                role: 'agent',
                content: streamingText,
                offer_amount: null,
                offer_selection: null,
                action: null,
              }}
            />
          )}
          {isStreaming && !streamingText && (
            <p className="text-xs text-muted-foreground">Seller is typing…</p>
          )}
          {streamError && (
            <p className="text-xs text-destructive">{streamError}</p>
          )}
        </div>

        {status === 'accepted' && (
          <div className="border-t bg-accent p-4 text-sm font-bold text-accent-foreground">
            Offer accepted — transaction complete · Agreed at{' '}
            {formatGBP(negotiation?.agreed_price ?? 0)} for{' '}
            {describeSelection(negotiation?.current_selection)}
          </div>
        )}

        {status === 'rejected' && (
          <div className="space-y-3 border-t p-4">
            <p className="text-sm font-bold text-sale">Offer rejected</p>
            <div className="flex gap-2">
              <Button className="flex-1" onClick={onMakeNewOffer}>
                Make another offer
              </Button>
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => onOpenChange(false)}
              >
                End negotiation
              </Button>
            </div>
          </div>
        )}

        {status === 'open' && (
          <div className="space-y-3 border-t p-4">
            {lastCounter && !isStreaming && (
              <Button
                className="w-full bg-accent font-bold text-accent-foreground hover:bg-accent/90"
                disabled={accept.isPending}
                onClick={() => accept.mutate()}
              >
                {accept.isPending
                  ? 'Accepting…'
                  : `Accept seller's offer · ${formatGBP(lastCounter.offer_amount ?? 0)} for ${describeSelection(lastCounter.offer_selection)}`}
              </Button>
            )}
            {accept.isError && (
              <p className="text-xs text-destructive">
                Could not accept the offer. Try again.
              </p>
            )}
            <div className="flex items-end gap-2">
              <Textarea
                placeholder="Message the seller…"
                rows={2}
                className="min-h-16 flex-1 resize-none text-[15px]"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    if (!isStreaming) send()
                  }
                }}
              />
              <Button size="lg" onClick={send} disabled={isStreaming}>
                Send
              </Button>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm text-muted-foreground">Offer £</span>
              <Input
                type="number"
                min={1}
                step="0.01"
                placeholder="optional"
                className="h-9 w-32"
                value={draftOffer}
                onChange={(e) => setDraftOffer(e.target.value)}
              />
              {grades.length > 1 && draftOffer.trim() !== '' && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setEditScope((v) => !v)}
                >
                  {editScope ? 'Keep current pieces' : 'Change pieces'}
                </Button>
              )}
            </div>
            {editScope && draftOffer.trim() !== '' && (
              <div className="rounded-lg border p-3">
                <GradePicker
                  grades={grades}
                  maxPieces={item.piece_count}
                  quantities={quantities}
                  onChange={setQuantities}
                />
                <p className="mt-2 text-xs text-muted-foreground">
                  Leave all at 0 to keep the current scope.
                </p>
              </div>
            )}
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}

function MessageBubble({ message }: { message: LocalMessage }) {
  const isBuyer = message.role === 'buyer'
  const offerLabel = message.action === 'counter' ? 'Counter' : 'Offer'
  return (
    <div className={cn('flex', isBuyer ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[85%] rounded-lg px-3.5 py-2.5 text-[15px] leading-relaxed',
          isBuyer ? 'bg-primary text-primary-foreground' : 'bg-muted',
        )}
      >
        {message.offer_amount != null && (
          <p className="font-bold">
            {offerLabel}: {formatGBP(message.offer_amount)}
            {message.offer_selection && message.offer_selection.length > 0 && (
              <span className="font-normal opacity-80">
                {' '}
                · {describeSelection(message.offer_selection)}
              </span>
            )}
          </p>
        )}
        {message.content && <p>{message.content}</p>}
      </div>
    </div>
  )
}
