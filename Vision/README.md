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

## MVP

- Upload a supplier video
- Detect garments automatically
- Segment each garment
- Track garments across frames
- Export one clean image per garment
- Generate metadata using a Vision-Language Model

## Stretch Goals

- Remove duplicate detections
- Select the sharpest frame automatically
- OCR labels and tags
- Detect visible defects
- Estimate garment condition
- Generate structured listings

## Candidate Models

- Grounding DINO
- SAM 2
- Grounded SAM 2
- Florence-2
- Qwen2.5-VL
- Gemini Vision
- OpenCV

