# Seller agent

LLM seller that haggles per turn: builds context → structured decision →
policy guardrails → streamed reply.

| Module | Role |
|---|---|
| `context.py` | Pluggable prompt blocks (`CONTEXT_PROVIDERS`) |
| `negotiator.py` | One turn: decide, guard, persist, stream |
| `policy.py` | Hard rules (never below floor, firm price, etc.) |
| `pricing.py` | Bundle / grade pricing helpers |
| `prompts.py` | Persona + output format |
| `schemas.py` | Structured LLM decision shape |

To add a new context source, write a `ContextProvider` and append it to
`CONTEXT_PROVIDERS` in `context.py`.

## What the negotiator uses

| Block | Source | Contents |
|---|---|---|
| Persona | `prompts.py` | Seller voice (`vendor_name`) |
| **The listing** | `Item` | `title`, `brand`, `condition`, `category`, `sizes`, `piece_count`, asking `bundle_price` / `price_per_piece`, `description`, optional original/discount |
| **Vision signals** | `Item.vision_signals` | Stance, defects, talking points, objection risks, needs_review |
| **Stock by grade** | `Item.grades` | Per-grade counts, prices, confidential floors |
| **Haggle policy** | `Item` + selection | `buying_price`, bundle/grade floors, `negotiable`, `high_quantity`, current selection asking/floor |
| **Negotiation state** | `Negotiation` + messages | Round count, standing offer / selection |
| Output format | `prompts.py` | Structured decision shape |

```text
Item DB / haggle policy  →  WHAT we can sell for (asking, floor, firm?)
Vision signals           →  HOW hard we push + WHAT we admit from the photo
```

Canonical listing copy, prices, floors, and stock stay on `Item`. Vision only
adds seller-side photo awareness.

## Vision signals (additive, seller-side)

Filled at merchant publish from `listings.json` via
`app.merchant.vision_signals.aggregate_vision_signals` → `Item.vision_signals`
(JSONB, confidential like floors). Not on public `ItemRead`.

Purpose: help the seller agent answer buyers with photo-grounded honesty.
Example: a visible stain → don’t push back as hard; acknowledge the defect.

### Include

| Field | Meaning | Effect on the agent |
|---|---|---|
| `defect_severity` + `defects_visible` | `none` / `minor` / `major` and what’s wrong | Clean → defend; stained/damaged → concede sooner, stay honest |
| `talking_points` (≤3) | Concrete facts from the photo | Specific seller lines (“logo clear”, “zipper intact”) |
| `buyer_objection_risks` (≤3) | What the buyer will poke at | Pre-empt (“as shown”, “size not on tag”) |
| `suggested_stance` | `firm` / `balanced` / `flexible` | Tone bias only — policy/floor still wins |
| `needs_review` | Frame/attributes are uncertain | Soften claims; avoid absolutes |

### Do not feed / do not override

Already owned by listing + haggle policy:

- title, brand, category, condition, description
- asking prices, `buying_price`, floors, `negotiable`, `high_quantity`, grades

Skip as negotiation noise: `brand_tier`, `color_primary`, `color_secondary`,
`pattern`, `visible_text`, `crop_path`, `model`, `error`.

### Prompt block (`vision_signals_block`)

```text
## Vision signals (seller-side — additive, does not override listing or floors)
stance: flexible
defects: stain on lower front (minor)
talking_points: ["brand logo visible", "zipper intact"]
buyer_objection_risks: ["visible stain", "size not readable"]
needs_review: false
```

If `vision_signals` is null (manual listings), the block is omitted and the
agent behaves as before. Policy and pricing remain authoritative.
