import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import items, merchant, negotiations

logging.basicConfig(level=logging.INFO)

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Fleek Buddy API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(items.router, prefix="/api")
app.include_router(negotiations.router, prefix="/api")
app.include_router(merchant.router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
