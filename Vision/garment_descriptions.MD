# VLM Garment Extraction: Output Specification

## Purpose

This document defines exactly what the VLM must return for each isolated
garment frame. The output feeds three downstream consumers: a pricing
negotiation view, a condition/quality grading view, and a buyer-facing
summary. The model must never guess silently — every field must expose
its own confidence and visibility state so the UI can distinguish
"confidently known," "visible but uncertain," and "not visible."

**The model only ever sees a single isolated frame
of the full garment (from unpiling video), never a tag or label
close-up.** Everything is based on the garment's
outward appearance alone — silhouette, fabric look, color, visible
branding printed/embroidered/woven into the garment itself, and
construction/condition visible at whole-garment distance. There is no
tag-reading step. Fields that would normally come from a care label
(fiber content %, country of origin, size-from-tag, "new with tags"
stickers) are intentionally excluded.

Source frames also carry the usual problems of unpiling footage: motion
blur, partial occlusion, inconsistent lighting, and a garment that may be
folded, twisted, or only partly unfurled. The output format is designed
around that constraint.

## Output format rules

- Always return **strict JSON**, no markdown fences, no preamble text.
- Every extracted attribute is an **object**, never a bare value:
  `{ "value": ..., "confidence": "...", "visible": true/false }`
- If a field cannot be determined, set `"value": null` and use a
  `reason_code` (see below) instead of guessing a plausible-sounding answer.
- `confidence` is always one of: `"high"`, `"medium"`, `"low"`. Do not
  invent other confidence labels.
- `visible` is `true` if the relevant part of the garment is in frame at
  all (even if unclear), `false` if it's simply not in frame or occluded
  (e.g. garment is folded so the back isn't visible).
- Only the final `buyer_summary` field is free text. Every other field
  must be a controlled value or short factual phrase, not a sentence.

### `reason_code` values (used whenever `value` is null)

| Code | Meaning |
|---|---|
| `occluded` | Relevant area is blocked by folds, other garments, hands, or the garment's own bunching |
| `out_of_frame` | Relevant area isn't captured in the frame (e.g. garment back, inside lining) |
| `insufficient_image_quality` | Blur/lighting/resolution prevents a confident read |
| `detail_not_resolvable` | Frame resolution/distance is too low to judge fine detail (stitching, small hardware, fabric weave) even though the general area is visible |
| `not_applicable` | Attribute doesn't apply to this garment type |
| `no_branding_visible` | No logo, print, or embroidery is visible anywhere on the garment |

---

## Field groups

### 1. Identification

| Field | Type | Subcategory notes |
|---|---|---|
| `garment_type` | enum | top, t-shirt, shirt, blouse, sweater, hoodie, jacket, coat, blazer, dress, skirt, trousers, jeans, shorts, jumpsuit, activewear, underwear/loungewear, swimwear, other |
| `subtype` | short string | Constrained to known silhouette vocabulary per `garment_type`, e.g. jeans → skinny/straight/bootcut/wide-leg/mom; jacket → bomber/trucker/blazer/puffer/parka; dress → maxi/midi/mini/wrap/shift |
| `age_segment` | enum | adult, kids, baby, unknown |


### 2. Visible Branding (replaces tag-based brand ID)

| Field | Type | Notes |
|---|---|---|
| `logo_or_print_visible` | boolean | Any brand mark, printed graphic, or embroidered logo visible anywhere on the garment exterior |
| `brand_name_from_visible_mark` | string or null | Only populate if a logo/wordmark on the garment itself is legible (e.g. an embroidered chest logo or woven waistband text) — this is different from a sewn-in tag, which is never visible in this pipeline. If no such mark or it's illegible, `null` with the relevant reason code. |
| `brand_tier_impression` | enum | `premium`, `mid`, `mass_market`, `unknown` — only set from visible construction/logo cues, flagged clearly as an impression, not a verified brand tier |

### 3. Material & Construction (visual only)

| Field | Type | Notes |
|---|---|---|
| `fabric_primary` | string | Visual estimate from texture/drape/sheen (cotton, denim, polyester, wool-look, linen, leather/faux-leather, knit, fleece, etc.). Always `basis: "visual_texture_inference"` — there is no care label to confirm against, so this must never exceed `confidence: "medium"`. |
| `fabric_secondary` | string or null | Visible trim, lining edge, or contrast panel material, if visible |
| `weight_season_impression` | enum | lightweight/summer, mid-weight/transitional, heavyweight/winter — based on drape and visible thickness |
| `lining_visible` | boolean | Only `true` if lining is actually visible (open jacket, exposed hem) — otherwise `null` with `out_of_frame` |
| `hardware_visible` | string or null | Short factual note on visible zippers/buttons/snaps and their apparent condition, only for hardware actually in frame |
| `stitching_quality_impression` | string or null | Short factual note only, and only if seams are resolvable at frame resolution — otherwise `null` with `detail_not_resolvable` |

### 4. Condition (core grading sectionvisual only)

| Field | Type | Notes |
|---|---|---|
| `defects` | array of objects | See defect taxonomy below. Empty array if none observed — do not omit the key. Only log defects actually visible in this frame; do not infer likely defects on unseen parts (e.g. don't assume a stain on the back if the back isn't in frame). |
| `repairs_alterations_visible` | boolean | Visible mending, resizing, patch, replaced button, etc. — only if visible in this frame |
| `image_quality_flag` | object | `{ "motion_blur": bool, "occlusion": bool, "lighting": "poor"/"adequate"/"good", "garment_fully_unfurled": bool, "affects_fields": [list of field paths whose confidence was capped by image/pose quality] }` |

**Defect object structure:**
```json
{
  "type": "stain | hole | tear | fading | pilling | stretching | missing_hardware | broken_zip | discoloration | snag | shrinkage_impression | wrinkling_creasing",
  "location": "collar | cuffs | hem | underarm | elbows | knees | seams | front_panel | back_panel | pockets | overall | other",
  "severity": "minor | moderate | severe",
  "confidence": "high | medium | low",
  "note": "optional short factual clarifier, e.g. 'may be shadow or fold, verify manually'"
}
```
Rules for defects:
- Every defect must have both `type` and `location`.
- If unsure whether something is a defect vs. a shadow/fold/lighting artifact (very common on unpiling footage where garments are mid-motion), still log it but set `confidence: "low"` and add a `note` — never silently drop a possible defect, and never silently upgrade a maybe into a confident claim.
- Do not log defects for parts of the garment that are folded/twisted/out of frame — use `image_quality_flag.garment_fully_unfurled: false` to signal that condition assessment is necessarily partial.

### 5. Aesthetic / Merchandising

| Field | Type | Notes |
|---|---|---|
| `color_primary` | string | Common color name, not a hex code |
| `color_secondary` | string or null | |
| `pattern` | enum | solid, stripe, plaid, floral, graphic_print, animal_print, colorblock, other |
| `notable_features` | array of strings | Embroidery, distressing, branded print, unusual trim, statement hardware — anything visible that could add resale value |
| `style_era_impression` | enum | vintage-cue, retro-influenced, contemporary, unknown |


## General behavioral rules for the model

1. **Never trade a null for a guess.** A low-confidence "unknown" is more useful to a negotiation tool than a fabricated specific answer — this applies especially to `brand_name_from_visible_mark`, `size_estimate`, and `fabric_primary`.
2. **Everything must be traceable to this one frame.** Do not infer facts that would require a tag, label, or second angle you don't have. If a downstream user asks "how do you know that," the answer must always be "visible in the frame," never "typical for this brand/category."
3. **One garment per output object.** If multiple items are visible in a frame, either flag `multiple_items_detected: true` at the top level and describe only the primary/foreground item, or (if the pipeline supports it) return an array with one object per item.
4. **Keep all non-summary fields terse and factual.** No adjectives like "beautiful" or "stylish" outside `notable_features` and `buyer_summary`.
5. **Do not infer brand tier, price band, or style era from stereotypes about garment type alone** — these must be grounded in what's actually visible (logo, construction quality, fabric appearance).
6. **A partially unfurled or folded garment yields a partial assessment, not a completed one.** Set `image_quality_flag.garment_fully_unfurled: false` whenever relevant, and let confidence and `fields_needing_human_review` reflect that honestly rather than filling gaps with assumptions.