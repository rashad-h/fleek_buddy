# Vision

This folder holds vision docs and materials for Fleek Buddy.

It is intentionally isolated at the repo root to reduce merge conflicts with application code and other workstreams.

# Video2Catalog

> Turn a supplier video into clean, per-item listings.

## Problem

FleekSort generates structured listings from a few product photos.

However, suppliers often start with a continuous video or a quick walkthrough of hundreds of garments. Before any cataloging can happen, each individual garment must first be isolated from the video.

This step is currently manual, time-consuming, and difficult because garments overlap, move, deform, and appear only briefly.

## Our Goal

Build an AI pipeline that converts a supplier video into isolated garment assets that can be directly consumed by FleekSort.

## Why this matters

Video capture is significantly faster than photographing every individual item.

Automating the transition from video → isolated garments enables:

- faster supplier onboarding
- lower cataloging costs
- higher throughput
- cleaner downstream listings
- easier integration with existing pricing and catalog pipelines

## Pipeline

Specialize early, generalize late: detectors/trackers find garments over time; VLMs describe only the final stills.

```text
Video + text prompts
  → SAM 3 (HF) detect + segment + track
  → best-frame pick + crop
  → dedupe tracks
  → VLM metadata on final crops
  → FleekSort handoff
```

| Stage | Model | Job |
|---|---|---|
| Detect + segment + track | **SAM 3** (`facebook/sam3` via Transformers) | Primary spine — try first |
| Fallback | Grounded SAM 2 | If SAM 3 setup/quality fails |
| Best frame / quality | OpenCV heuristics | Sharpness, size, occlusion |
| Dedupe | CLIP / SigLIP | Merge near-duplicate tracks |
| Attributes | Qwen2.5-VL or Gemini | Category, color, type on final crops only |

Code + isolated env: [`Vision/sam3/`](sam3/).

## MVP

- Upload a supplier video
- SAM 3 text prompts → tracks with stable IDs → best crop per track
- Dedupe near-identical tracks
- VLM metadata (category / color / type)
- Export bundle for FleekSort (`crop`, optional mask, `quality_score`, timestamp)
- `needs_review` queue for low-confidence tracks

## Stretch Goals

- OCR labels and tags
- Detect visible defects
- Estimate garment condition
- Background matting polish
- Generate full structured listings

## Design tips

- Best-frame selection and dedupe are MVP — random frames poison FleekSort.
- Sample adaptively (more frames on motion/content change); do not run dense detection every frame.
- Define the FleekSort input contract early (1–3 crops/item, quality score, source timestamp).
- Ship human review for merge/split/reject before chasing perfect automation.
- Light capture guidance (pause on each item, avoid piles/extreme motion) beats a bigger model on messy walkthroughs.
- Defer defects/condition — hard and subjective; isolation quality first.
