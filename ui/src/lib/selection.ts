import type { OfferSelection } from '#/lib/types.ts'

/**
 * Grades offered by a listing, parsed from its condition label
 * ("AB Grade Vintage" -> A, B). Per-grade counts are seller-only; buyers
 * pick quantities blind and the seller corrects availability in chat.
 */
export function gradesFromCondition(condition: string): Array<string> {
  const match = condition.toUpperCase().match(/^([ABC]{1,3})\s+GRADE/)
  return match ? [...new Set(match[1].split(''))] : ['A', 'B', 'C']
}

export function describeSelection(
  selection: Array<OfferSelection> | null | undefined,
): string {
  if (!selection || selection.length === 0) return 'full bundle'
  return selection
    .map((entry) => `${entry.quantity}× Grade ${entry.grade}`)
    .join(' + ')
}

export function selectionPieces(selection: Array<OfferSelection>): number {
  return selection.reduce((sum, entry) => sum + entry.quantity, 0)
}

/** Quantities keyed by grade -> API selection (drops zero lines). */
export function toSelection(
  quantities: Record<string, number>,
): Array<OfferSelection> {
  return Object.entries(quantities)
    .filter(([, quantity]) => quantity > 0)
    .map(([grade, quantity]) => ({ grade, quantity }))
}
