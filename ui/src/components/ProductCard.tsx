import { formatGBP } from '#/lib/format.ts'

import type { Item } from '#/lib/types.ts'

export function ProductCard({ item }: { item: Item }) {
  return (
    <div className="group overflow-hidden rounded-lg border bg-card shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md">
      <div className="relative aspect-square overflow-hidden bg-muted">
        <img
          src={item.image_url}
          alt={item.title}
          className="h-full w-full object-cover transition-transform group-hover:scale-[1.02]"
        />
        {item.discount_percent != null && (
          <span className="absolute top-2 left-2 rounded-md bg-sale px-2 py-0.5 text-xs font-bold text-white">
            -{item.discount_percent}%
          </span>
        )}
      </div>
      <div className="space-y-1 p-3">
        <p className="truncate text-sm font-semibold">{item.title}</p>
        <p className="truncate text-xs text-muted-foreground">
          {item.vendor_name}
        </p>
        <p className="text-base font-bold">
          {formatGBP(item.price_per_piece)}
          <span className="text-sm font-semibold">/pc</span>
        </p>
        <p className="text-sm text-muted-foreground">
          {formatGBP(item.bundle_price)}
          {item.original_price != null && (
            <span className="ml-1.5 line-through opacity-70">
              {formatGBP(item.original_price)}
            </span>
          )}
        </p>
        <div className="flex items-center justify-between">
          <p className="text-xs text-muted-foreground">Shipping Inc.</p>
          {item.negotiable && (
            <span className="rounded-sm bg-accent/20 px-1.5 py-0.5 text-[10px] font-bold text-accent-foreground">
              Open to offers
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
