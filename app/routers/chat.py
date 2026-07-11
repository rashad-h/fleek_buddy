from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app import llm
from app.schemas import ChatRequest

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("")
async def chat(request: ChatRequest) -> dict[str, str]:
    messages = [m.model_dump() for m in request.messages]
    return {"content": await llm.complete(messages)}


@router.post("/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    messages = [m.model_dump() for m in request.messages]
    return StreamingResponse(llm.stream(messages), media_type="text/plain")
