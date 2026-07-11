import { useEffect, useState } from 'react'

import { merchantImageUrl } from '#/lib/merchant-api.ts'
import type { MerchantItem } from '#/lib/merchant-types.ts'

function formatCondition(value: string): string {
  return value.replaceAll('_', ' ')
}

export function GarmentCard({ item }: { item: MerchantItem }) {
  const [title, setTitle] = useState(item.attributes?.short_title ?? '')
  const [description, setDescription] = useState(item.attributes?.description ?? '')

  const attrs = item.attributes

  useEffect(() => {
    if (attrs) {
      setTitle(attrs.short_title)
      setDescription(attrs.description)
    }
  }, [attrs])

  const isLoading = item.status === 'pending' || item.status === 'analyzing'
  const hasError = item.status === 'error'

  return (
    <article className="overflow-hidden rounded-lg border bg-card shadow-sm">
      <div className="relative aspect-square overflow-hidden bg-muted">
        <img
          src={merchantImageUrl(item.image_url)}
          alt={attrs?.short_title ?? item.filename}
          className="h-full w-full object-cover"
        />
        {attrs?.needs_review && (
          <span className="absolute top-2 left-2 rounded-md bg-sale px-2 py-0.5 text-xs font-bold text-white">
            Needs review
          </span>
        )}
      </div>
      <div className="space-y-2 p-3">
        {isLoading ? (
          <>
            <div className="h-4 w-3/4 animate-pulse rounded bg-muted" />
            <div className="h-3 w-1/2 animate-pulse rounded bg-muted" />
            <div className="h-12 w-full animate-pulse rounded bg-muted" />
          </>
        ) : hasError ? (
          <p className="text-sm text-destructive">{item.error ?? 'Analysis failed'}</p>
        ) : attrs ? (
          <>
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              className="w-full border-0 bg-transparent p-0 text-sm font-semibold outline-none focus:ring-0"
              aria-label="Listing title"
            />
            <p className="text-xs text-muted-foreground">
              {attrs.category}
              {attrs.subcategory ? ` · ${attrs.subcategory}` : ''}
            </p>
            <p className="text-xs text-muted-foreground">
              {attrs.color_primary} · {formatCondition(attrs.condition_visible)}
              {attrs.material_guess && attrs.material_guess !== 'unknown'
                ? ` · ${attrs.material_guess}`
                : ''}
            </p>
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={3}
              className="w-full resize-none rounded-md border border-input bg-background px-2 py-1.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
              aria-label="Listing description"
            />
          </>
        ) : null}
      </div>
    </article>
  )
}
