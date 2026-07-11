#!/usr/bin/env python3
"""Build a self-contained HTML gallery from extract.py output."""

from __future__ import annotations

import argparse
import base64
import mimetypes
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a self-contained HTML gallery of extracted item frames.",
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Folder containing item_XXX.jpg (+ optional .sharpness.txt)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="HTML file path (default: <input>/gallery.html)",
    )
    return parser.parse_args()


def load_sharpness(image_path: Path) -> str:
    meta = image_path.with_suffix(".sharpness.txt")
    # item_001.jpg → item_001.sharpness.txt
    alt = image_path.parent / f"{image_path.stem}.sharpness.txt"
    for candidate in (meta, alt):
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8").strip()
    return "—"


def data_uri(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    mime = mime or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def build_html(items: list[tuple[str, str, str]]) -> str:
    cards = []
    for filename, sharpness, uri in items:
        cards.append(
            f"""
      <figure class="card">
        <img src="{uri}" alt="{filename}" loading="lazy" />
        <figcaption>
          <span class="name">{filename}</span>
          <span class="score">sharpness: {sharpness}</span>
        </figcaption>
      </figure>"""
        )

    cards_html = "\n".join(cards) if cards else "<p class='empty'>No images found.</p>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Extracted items — {len(items)}</title>
  <style>
    :root {{
      --bg: #f4f2ee;
      --ink: #1a1a1a;
      --muted: #666;
      --line: #ddd8d0;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      padding: 2rem 1.25rem 3rem;
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--ink);
    }}
    header {{
      max-width: 1200px;
      margin: 0 auto 1.75rem;
    }}
    h1 {{
      margin: 0 0 0.35rem;
      font-size: 1.5rem;
      font-weight: 600;
      letter-spacing: -0.02em;
    }}
    .meta {{
      margin: 0;
      color: var(--muted);
      font-size: 0.95rem;
    }}
    .grid {{
      max-width: 1200px;
      margin: 0 auto;
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 1.25rem;
    }}
    .card {{
      margin: 0;
      background: #fff;
      border: 1px solid var(--line);
      overflow: hidden;
    }}
    .card img {{
      display: block;
      width: 100%;
      aspect-ratio: 3 / 4;
      object-fit: cover;
      background: #e8e4dc;
    }}
    figcaption {{
      display: flex;
      flex-direction: column;
      gap: 0.15rem;
      padding: 0.65rem 0.75rem 0.8rem;
      font-size: 0.8rem;
    }}
    .name {{
      font-weight: 600;
      word-break: break-all;
    }}
    .score {{
      color: var(--muted);
    }}
    .empty {{
      grid-column: 1 / -1;
      color: var(--muted);
    }}
  </style>
</head>
<body>
  <header>
    <h1>Extracted items</h1>
    <p class="meta">{len(items)} image{"s" if len(items) != 1 else ""}</p>
  </header>
  <div class="grid">
{cards_html}
  </div>
</body>
</html>
"""


def main() -> int:
    args = parse_args()

    if not args.input.is_dir():
        print(f"Error: input folder not found: {args.input}", file=sys.stderr)
        return 1

    images = sorted(args.input.glob("item_*.jpg"))
    items: list[tuple[str, str, str]] = []
    for img in images:
        items.append((img.name, load_sharpness(img), data_uri(img)))

    out = args.output or (args.input / "gallery.html")
    out.write_text(build_html(items), encoding="utf-8")
    print(f"Wrote {out.resolve()} ({len(items)} images)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
