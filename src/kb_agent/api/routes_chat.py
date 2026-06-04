import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from kb_agent.api.dependencies import AppContainer, get_container
from kb_agent.api.schemas import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, container: AppContainer = Depends(get_container)) -> ChatResponse:
    result = container.agent.answer(request.app_id, request.message)
    return ChatResponse(session_id=request.session_id, result=result)


@router.post("/chat/stream")
def chat_stream(request: ChatRequest, container: AppContainer = Depends(get_container)) -> StreamingResponse:
    result = container.agent.answer(request.app_id, request.message)

    def events() -> Iterator[str]:
        for paragraph in result.answer.split("\n\n"):
            yield f"data: {json.dumps({'type': 'token', 'text': paragraph + chr(10) + chr(10)})}\n\n"
        yield f"data: {json.dumps({'type': 'final', 'payload': result.model_dump()})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")

