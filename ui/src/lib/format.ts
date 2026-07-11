const gbp = new Intl.NumberFormat('en-GB', {
  style: 'currency',
  currency: 'GBP',
})

export function formatGBP(amount: number): string {
  return gbp.format(amount)
}

export function perPiece(bundlePrice: number, pieceCount: number): string {
  if (pieceCount <= 0) return formatGBP(0)
  return `${formatGBP(bundlePrice / pieceCount)}/pc`
}
