# Fleek Buddy — Demo Script

Live walkthrough for judges. Target: **8–10 minutes**. Story: video becomes inventory, inventory becomes a deal — same metadata powers both.

**One-liner:** We turn a supplier haul video into a wholesale listing, then let an LLM seller negotiate it using photo-grounded signals and hard price floors.

---

## Pre-demo (T−10 min)

Do this before anyone is watching.

1. Confirm Docker Desktop is running (`docker --version` works).
2. Root `.env` has an LLM key **and** `GEMINI_API_KEY`.
3. Vision envs exist: `make setup-vision-envs` (once).
4. Fresh stack:

```bash
make nuke          # optional: clean DB
# terminal 1
make dev-merchant
# terminal 2
make dev-backend-host
# terminal 3 (after API is up)
make seed
```

5. Smoke checks:
   - http://localhost:3000 — product cards load
   - http://localhost:3000/merchant — upload UI loads
   - Dry-run one short haggle on **Under Armour Sexy Shorts** until accept
   - Optional: start a sample video job so frames are warm / you know latency

6. Browser: one window on `/merchant`, one on `/` (or two tabs). Zoom readable for the projector.

**If Gemini is slow:** leave item count at **auto** or set **Expected items** to something small (e.g. 6–8) so describe finishes during the pitch.

---

## Act 0 — Pitch (30–45 sec)

**Say:**

> Wholesale resale is stuck in two places. Cataloging a haul video is manual and slow. Negotiating every offer does not scale. Fleek Buddy closes both: film once, isolate garments, extract listing metadata, publish a bundle, then an always-on seller agent haggles using the same photo signals — with floors enforced in code, not hope.

**Show (optional slide / README value map):**

```text
Video → isolate → Gemini metadata → publish → buyer offer → negotiate
```

---

## Act 1 — Merchant: video → listing (~3–4 min)

**Go to:** http://localhost:3000/merchant

### Step 1 — Upload

1. Click **Use demo sample** (do not dig for a file unless you want to show a custom clip).
2. Leave **Expected items** blank (auto) unless you pre-tuned a smaller N for speed.

**Say while it starts:**

> Suppliers already shoot walkthrough videos. We do not ask for a studio shoot per piece. The pipeline pulls garment frames, then Gemini describes each one live.

### Step 2 — Isolation (frames appear)

Watch status → **Extracting…** then garment cards with images.

**Say:**

> This is the hard part of video cataloging — finding each item in a messy haul. Isolation is what saves the supplier hours.

### Step 3 — Metadata (cards fill in)

As SSE events land, point at a couple of cards: brand, color, condition, defects, short title, confidence / needs review.

**Say:**

> Each frame becomes structured metadata: catalog fields for the listing, plus seller-side signals — talking points, buyer objection risks, and a suggested negotiation stance. One upload feeds both the storefront and the haggler.

### Step 4 — Bundle summary + publish

When status is complete, show the **bundle summary** (title, brands, highlights, piece count).

1. Click **Publish bundle to marketplace**.
2. Confirm “Published 1 bundle listing” and follow **View on marketplace** (or open `/`).

**Say:**

> Publish creates a real wholesale item: buyer-facing copy and images, plus confidential floors, grade stock, and vision signals the public API never exposes.

---

## Act 2 — Marketplace: what buyers see (~1 min)

**Go to:** http://localhost:3000

1. Find the new **Video Catalog** listing (or refresh if needed).
2. Open it. Scroll images from the haul frames and the auto-written description / includes list.

**Say:**

> Same frames buyers browse are the frames Gemini analyzed. Catalog quality is not a separate human typing step.

Optional beat: glance at seeded cards (**Under Armour Sexy Shorts**, etc.) to show this is a full Fleek-style wholesale UI, not a one-off prototype screen.

---

## Act 3 — Negotiate the video listing (~3 min)

Stay on the **published video bundle**.

### Beat A — Lowball

1. **Make an offer** — open around **~40–50% of asking** (deliberately low).
2. Chat drawer opens; seller streams a counter.

**Say:**

> Live SSE chat. The agent has personality, but policy clamps anything below the floor. Vision can make it more flexible if the haul shows defects — floors still win.

### Beat B — Photo honesty

In chat, ask something like:

> “Any stains or damage I should know about?”

**Say if it cites defects / “as shown”:**

> That answer is grounded in Gemini vision signals from the upload — not invented catalog fluff.

**If the sample looks clean:** still ask; agent may say stock looks good / no major defects. Point out stance can stay firmer when photos are clean.

### Beat C — Grade play (optional if time)

1. Toggle **Offer on specific grades only**.
2. Ask for a subset (e.g. mostly A-grade).
3. Send a mid offer.

**Say:**

> Buyers can bid on grade mixes, not only the full lot. The seller prices that scope, can upsell other grades, and never invents stock it does not hold.

### Beat D — Close

Either:

- Hit **Accept seller's offer**, or
- Offer a number near the last counter so it accepts.

Show the deal-complete / locked chat state.

**Say:**

> Deal locked. Always-on seller, margin protected.

---

## Act 4 — Contrast: firm price (~45–60 sec)

**Go to:** dashboard → **The North Face Fleeces** (seeded `negotiable=false`).

1. Open it → **Make an offer** → lowball hard.
2. Show it holding firm / refusing to chase the lowball.

**Say:**

> Same agent stack. Non-negotiable stock short-circuits soft LLM improvisation. Policy is code, not vibes. That is how you trust this in production.

---

## Act 5 — Close (~20–30 sec)

**Say:**

> Fleek Buddy is the connective tissue between how inventory enters the marketplace and how it gets sold. Faster supplier onboarding, richer listings, and a negotiator that already knows what the photos show.

Invite questions. Backup talking points below if asked.

---

## Timing cheat sheet

| Block | Time | Screen |
|---|---|---|
| Pitch | 0:45 | Talk / diagram |
| Video upload → frames → Gemini | 3:00 | `/merchant` |
| Publish + buyer listing | 1:00 | `/` + item |
| Haggle video item | 3:00 | item + drawer |
| North Face firm | 0:45 | North Face item |
| Close | 0:30 | — |

If Gemini is still running during Act 1, keep talking value (isolation + dual-use metadata) while cards populate. Do not wait in silence.

---

## Backup paths

| Problem | Move |
|---|---|
| Video job fails / no Gemini | Skip to seeded **Under Armour Sexy Shorts** for full haggle; still pitch Vision as the catalog path and show `/merchant` UI + README diagram |
| Describe too slow | Pre-run sample before judges; or lower expected item count; narrate over progress |
| Agent canned / no LLM key | Fix key; North Face firm-price still demos policy without a clever chat |
| Publish listing hard to find | Sort/refresh dashboard; vendor **Video Catalog** |
| Chat does not stream | Hard refresh; confirm host API on `:8000` with `make dev-backend-host` |

### Seeded haggle script (fallback / warm-up)

1. Open **Under Armour Sexy Shorts** (~£120 bundle).
2. Offer **£70** → counter (floor ~£96, small flex allowed).
3. Offer **£100** or **Accept seller's offer**.
4. Optional: **Nike Vintage Tees Mix** → grade-only offer 10× A + 5× B.

---

## Judge Q&A — short answers

**What is unique?**  
Closed loop: vision output is not a dead JSON dump — it changes how the seller negotiates.

**Does the buyer see floors / vision?**  
No. Public API strips seller secrets. Vision is seller-side only.

**Can the agent sell below cost?**  
No meaningful undercut of the floor; code clamps accepts/counters. Tiny closing flex only.

**SAM 3 vs what we just ran?**  
Merchant demo uses fast frame extract + Gemini. SAM 3 is the heavier isolation spine for Video2Catalog research; same product story.

**What did we save the supplier?**  
Per-item photoshoot + manual attribute typing. Film a haul → review → publish.

---

## URLs

| What | URL |
|---|---|
| Buyer marketplace | http://localhost:3000 |
| Merchant / video | http://localhost:3000/merchant |
| API docs | http://localhost:8000/docs |
