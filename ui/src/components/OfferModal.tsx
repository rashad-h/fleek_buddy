import { useForm } from '@tanstack/react-form'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { createNegotiation } from '#/lib/api.ts'
import { formatGBP, perPiece } from '#/lib/format.ts'
import { Button } from '#/components/ui/button.tsx'
import { Input } from '#/components/ui/input.tsx'
import { Label } from '#/components/ui/label.tsx'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '#/components/ui/dialog.tsx'

import type { Item, Negotiation } from '#/lib/types.ts'

type OfferModalProps = {
  item: Item
  buyerId: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: (negotiation: Negotiation) => void
}

export function OfferModal({
  item,
  buyerId,
  open,
  onOpenChange,
  onCreated,
}: OfferModalProps) {
  const queryClient = useQueryClient()

  const create = useMutation({
    mutationFn: createNegotiation,
    onSuccess: (negotiation) => {
      void queryClient.invalidateQueries({
        queryKey: ['negotiation', 'item', String(item.id), buyerId],
      })
      onOpenChange(false)
      onCreated(negotiation)
    },
  })

  const form = useForm({
    defaultValues: { offer: '', message: '' },
    onSubmit: async ({ value }) => {
      await create.mutateAsync({
        item_id: item.id,
        buyer_id: buyerId,
        offer_price: Number(value.offer),
        message: value.message.trim() || undefined,
      })
      form.reset()
    },
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Make an offer</DialogTitle>
          <DialogDescription>
            {item.title} · asking {formatGBP(item.bundle_price)} for{' '}
            {item.piece_count} pieces (shipping inc.)
          </DialogDescription>
        </DialogHeader>
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            void form.handleSubmit()
          }}
        >
          <form.Field
            name="offer"
            validators={{
              onChange: ({ value }) => {
                const amount = Number(value)
                if (value.trim() === '' || Number.isNaN(amount))
                  return 'Enter your offer in £'
                if (amount < 1) return 'Offer must be at least £1'
                return undefined
              },
            }}
          >
            {(field) => (
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="offer">Your offer for the bundle (£)</Label>
                <Input
                  id="offer"
                  type="number"
                  min={1}
                  step="0.01"
                  placeholder={String(item.bundle_price)}
                  value={field.state.value}
                  onChange={(e) => field.handleChange(e.target.value)}
                />
                {Number(field.state.value) >= 1 && (
                  <p className="text-xs text-muted-foreground">
                    That's {perPiece(Number(field.state.value), item.piece_count)}
                  </p>
                )}
                {field.state.meta.errors.length > 0 && (
                  <p className="text-xs text-destructive">
                    {field.state.meta.errors[0]}
                  </p>
                )}
              </div>
            )}
          </form.Field>
          <form.Field name="message">
            {(field) => (
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="offer-message">Message (optional)</Label>
                <Input
                  id="offer-message"
                  placeholder="Any context for the seller…"
                  value={field.state.value}
                  onChange={(e) => field.handleChange(e.target.value)}
                />
              </div>
            )}
          </form.Field>
          {create.isError && (
            <p className="text-xs text-destructive">
              Could not send the offer. Try again.
            </p>
          )}
          <Button type="submit" size="lg" disabled={create.isPending}>
            {create.isPending ? 'Sending…' : 'Send offer'}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  )
}
