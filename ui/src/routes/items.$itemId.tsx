import { useEffect, useState } from 'react'
import { createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'

import { fetchItem, fetchNegotiationForItem } from '#/lib/api.ts'
import { getBuyerId } from '#/lib/buyer.ts'
import { formatGBP } from '#/lib/format.ts'
import { Button } from '#/components/ui/button.tsx'
import { OfferModal } from '#/components/OfferModal.tsx'
import { NegotiationDrawer } from '#/components/NegotiationDrawer.tsx'

import type { Item, Negotiation } from '#/lib/types.ts'

export const Route = createFileRoute('/items/$itemId')({ component: ItemPage })

function ItemPage() {
  const { itemId } = Route.useParams()
  const [buyerId, setBuyerId] = useState('')
  const [offerOpen, setOfferOpen] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [activeNegotiationId, setActiveNegotiationId] = useState<number | null>(
    null,
  )
  const [autoRespond, setAutoRespond] = useState(false)

  useEffect(() => {
    setBuyerId(getBuyerId())
  }, [])

  const { data: item, isLoading } = useQuery({
    queryKey: ['item', itemId],
    queryFn: () => fetchItem(itemId),
  })

  const { data: negotiation } = useQuery({
    queryKey: ['negotiation', 'item', itemId, buyerId],
    queryFn: () => fetchNegotiationForItem(itemId, buyerId),
    enabled: buyerId !== '',
  })

  if (isLoading || !item) {
    return (
      <main className="mx-auto max-w-5xl px-6 py-12 text-center text-muted-foreground">
        {isLoading ? 'Loading…' : 'Item not found.'}
      </main>
    )
  }

  const openDrawerFor = (negotiationId: number, fresh: boolean) => {
    setActiveNegotiationId(negotiationId)
    setAutoRespond(fresh)
    setDrawerOpen(true)
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-8">
      <div className="grid gap-8 md:grid-cols-2">
        <div className="relative overflow-hidden rounded-lg border bg-muted">
          <img
            src={item.image_url}
            alt={item.title}
            className="aspect-square w-full object-cover"
          />
          {item.discount_percent != null && (
            <span className="absolute top-3 left-3 rounded-md bg-sale px-2.5 py-1 text-sm font-bold text-white">
              -{item.discount_percent}%
            </span>
          )}
        </div>
        <ItemSummary
          item={item}
          negotiation={negotiation ?? null}
          onMakeOffer={() => setOfferOpen(true)}
          onResume={(id) => openDrawerFor(id, false)}
        />
      </div>

      <OfferModal
        item={item}
        buyerId={buyerId}
        open={offerOpen}
        onOpenChange={setOfferOpen}
        onCreated={(created) => openDrawerFor(created.id, true)}
      />
      {activeNegotiationId != null && (
        <NegotiationDrawer
          item={item}
          negotiationId={activeNegotiationId}
          autoRespond={autoRespond}
          open={drawerOpen}
          onOpenChange={setDrawerOpen}
          onMakeNewOffer={() => {
            setDrawerOpen(false)
            setOfferOpen(true)
          }}
        />
      )}
    </main>
  )
}

function ItemSummary({
  item,
  negotiation,
  onMakeOffer,
  onResume,
}: {
  item: Item
  negotiation: Negotiation | null
  onMakeOffer: () => void
  onResume: (negotiationId: number) => void
}) {
  const chips = [
    `${item.piece_count} pieces`,
    item.condition,
    item.category,
    `Sizes ${item.sizes}`,
    ...(item.is_single_brand ? ['Single-brand bundle'] : []),
  ]

  return (
    <div className="flex flex-col gap-4">
      <div>
        <p className="text-sm text-muted-foreground">
          Sold by <span className="font-semibold">{item.vendor_name}</span>
        </p>
        <h1 className="mt-1 text-3xl font-extrabold tracking-tight">
          {item.title}
        </h1>
      </div>

      <div>
        <p className="text-3xl font-extrabold">
          {formatGBP(item.price_per_piece)}
          <span className="text-xl font-bold">/pc</span>
        </p>
        <p className="mt-1 text-muted-foreground">
          {formatGBP(item.bundle_price)} Bundle total · Shipping Inc.
          {item.original_price != null && (
            <span className="ml-2 line-through opacity-70">
              {formatGBP(item.original_price)}
            </span>
          )}
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {chips.map((chip) => (
          <span
            key={chip}
            className="rounded-md bg-muted px-2.5 py-1 text-xs font-semibold"
          >
            {chip}
          </span>
        ))}
      </div>

      <p className="text-sm leading-relaxed text-muted-foreground">
        {item.description}
      </p>

      <p className="text-sm text-muted-foreground">
        Ships in {item.shipping_days_min}–{item.shipping_days_max} working days
      </p>

      <OfferCta
        negotiation={negotiation}
        onMakeOffer={onMakeOffer}
        onResume={onResume}
      />
    </div>
  )
}

function OfferCta({
  negotiation,
  onMakeOffer,
  onResume,
}: {
  negotiation: Negotiation | null
  onMakeOffer: () => void
  onResume: (negotiationId: number) => void
}) {
  if (negotiation?.status === 'accepted') {
    return (
      <Button
        size="lg"
        className="w-full bg-accent text-accent-foreground hover:bg-accent-hover"
        onClick={() => onResume(negotiation.id)}
      >
        Deal agreed at {formatGBP(negotiation.agreed_price ?? 0)} · View
        conversation
      </Button>
    )
  }
  if (negotiation?.status === 'open') {
    return (
      <Button
        size="lg"
        className="w-full"
        onClick={() => onResume(negotiation.id)}
      >
        Resume negotiation
      </Button>
    )
  }
  return (
    <Button size="lg" className="w-full" onClick={onMakeOffer}>
      Make an offer
    </Button>
  )
}
