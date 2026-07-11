"""Default open-vocab garment prompts for SAM 3 video.

SAM 3 works best with short noun phrases, not instructions.
Run multiple categories in one pass, then dedupe tracks downstream.
"""

GARMENT_PROMPTS: list[str] = [
    "jacket",
    "coat",
    "shirt",
    "t-shirt",
    "hoodie",
    "sweater",
    "dress",
    "skirt",
    "trousers",
    "jeans",
]
