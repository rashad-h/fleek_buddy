export type JobStatus =
  | 'queued'
  | 'extracting'
  | 'describing'
  | 'summarizing'
  | 'complete'
  | 'error'

export type ItemStatus = 'pending' | 'analyzing' | 'complete' | 'error'

export type GarmentAttributes = {
  category: string
  subcategory: string | null
  brand: string | null
  color_primary: string
  material_guess: string
  condition_visible: string
  short_title: string
  description: string
  confidence: number
  needs_review: boolean
}

export type MerchantItem = {
  index: number
  filename: string
  image_url: string
  status: ItemStatus
  attributes: GarmentAttributes | null
  error: string | null
}

export type BundleSummary = {
  short_title: string
  description: string
  brands: Array<string>
  categories: Array<string>
  materials: Array<string>
  piece_count: number
  condition_overall: string
  highlights: Array<string>
  confidence: number
  needs_review: boolean
}

export type MerchantJob = {
  job_id: string
  status: JobStatus
  message: string
  items: Array<MerchantItem>
  summary: BundleSummary | null
  error: string | null
  published_item_ids: Array<number>
}

export type MerchantJobCreateResponse = {
  job_id: string
}

export type MerchantStatusEvent = {
  status: JobStatus
  message: string
}

export type MerchantFramesReadyEvent = {
  items: Array<MerchantItem>
}

export type MerchantItemAnalyzedEvent = {
  index: number
  filename: string
  attributes: GarmentAttributes | null
  error: string | null
}

export type MerchantSummaryReadyEvent = {
  summary: BundleSummary
}

export type MerchantErrorEvent = {
  detail: string
}

export type MerchantStreamHandlers = {
  onStatus: (event: MerchantStatusEvent) => void
  onFramesReady: (event: MerchantFramesReadyEvent) => void
  onItemAnalyzed: (event: MerchantItemAnalyzedEvent) => void
  onSummaryReady: (event: MerchantSummaryReadyEvent) => void
  onError: (detail: string) => void
  onDone: () => void
}
