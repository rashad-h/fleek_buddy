export type Item = {
  id: number
  title: string
  brand: string
  vendor_name: string
  description: string
  category: string
  condition: string
  sizes: string
  piece_count: number
  price_per_piece: number
  bundle_price: number
  original_price: number | null
  discount_percent: number | null
  shipping_days_min: number
  shipping_days_max: number
  is_single_brand: boolean
  image_url: string
  negotiable: boolean
  high_quantity: boolean
  created_at: string
}

export type NegotiationStatus = 'open' | 'accepted' | 'rejected'

export type MessageAction = 'offer' | 'counter' | 'accept' | 'reject' | 'chat'

/** One line of a partial offer; null selections mean the full bundle. */
export type OfferSelection = {
  grade: string
  quantity: number
}

export type Negotiation = {
  id: number
  item_id: number
  buyer_id: string
  status: NegotiationStatus
  current_offer: number | null
  current_selection: Array<OfferSelection> | null
  agreed_price: number | null
  created_at: string
  updated_at: string
}

export type Message = {
  id: number
  negotiation_id: number
  role: 'buyer' | 'agent' | 'system'
  content: string
  offer_amount: number | null
  offer_selection: Array<OfferSelection> | null
  action: MessageAction | null
  created_at: string
}

export type NegotiationDetail = Negotiation & { messages: Array<Message> }

export type DecisionEvent = {
  action: MessageAction
  price: number | null
  selection: Array<OfferSelection> | null
  status: NegotiationStatus
  message_id: number
}
