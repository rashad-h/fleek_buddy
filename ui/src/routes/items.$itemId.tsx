import { useEffect, useState } from 'react'
import { createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'

import { fetchItem, fetchNegotiationForItem } from '#/lib/api.ts'
import { getBuyerId } from '#/lib/buyer.ts'
import { formatGBP } from '#/lib/format.ts'
import { Button } from '#/components/ui/button.tsx'

import type { Item, Negotiation } from '#/lib/types.ts'

export const Route = createFileRoute('/items/$itemId')({ component: ItemPage })

function ItemPage() {
  const { itemId } = Route.useParams()
  const [buyerId, setBuyerId] = useState('')

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
        <ItemSummary item={item} negotiation={negotiation ?? null} />
      </div>
    </main>
  )
}

function ItemSummary({
  item,
  negotiation,
}: {
  item: Item
  negotiation: Negotiation | null
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

      <OfferCta item={item} negotiation={negotiation} />
    </div>
  )
}

function OfferCta({
  item,
  negotiation,
}: {
  item: Item
  negotiation: Negotiation | null
}) {
  void item
  if (negotiation?.status === 'accepted') {
    return (
      <Button
        size="lg"
        className="w-full bg-accent text-accent-foreground hover:bg-accent-hover"
      >
        Deal agreed at {formatGBP(negotiation.agreed_price ?? 0)} · View
        conversation
      </Button>
    )
  }
  if (negotiation?.status === 'open') {
    return (
      <Button size="lg" className="w-full">
        Resume negotiation
      </Button>
    )
  }
  return (
    <Button size="lg" className="w-full">
      Make an offer
    </Button>
  )
}
