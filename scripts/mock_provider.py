"""Tiny fake OpenAI-compatible provider for local testing.

Returns a fixed completion with a large usage block so budget counters move
visibly. Supports both non-streaming and SSE streaming (with a final usage
chunk + [DONE]). Run:  .venv\\Scripts\\python.exe scripts\\mock_provider.py
Then point the proxy at it with  OPENAI_BASE_URL=http://127.0.0.1:8200/v1
"""

import asyncio
import json

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI()

WORDS = ["Hello ", "from ", "the ", "mock ", "provider!"]

USAGE = {"prompt_tokens": 5000, "completion_tokens": 3000, "total_tokens": 8000}


def _chunk(model: str, delta: dict, finish_reason: str | None = None) -> str:
    return json.dumps(
        {
            "id": "chatcmpl-mock0001",
            "object": "chat.completion.chunk",
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": delta,
                    "finish_reason": finish_reason,
                }
            ],
        }
    )


async def _stream(model: str):
    """Yield SSE events with a pause so the client can watch chunks arrive."""
    yield f"data: {_chunk(model, {'role': 'assistant', 'content': ''})}\n\n".encode()
    for word in WORDS:
        yield f"data: {_chunk(model, {'content': word})}\n\n".encode()
        await asyncio.sleep(0.2)
    yield f"data: {_chunk(model, {}, 'stop')}\n\n".encode()
    yield _usage_chunk(model)
    yield b"data: [DONE]\n\n"


def _usage_chunk(model: str) -> bytes:
    payload = {
        "id": "chatcmpl-mock0001",
        "object": "chat.completion.chunk",
        "model": model,
        "choices": [],  # usage chunks carry no text, only totals
        "usage": USAGE,
    }
    return f"data: {json.dumps(payload)}\n\n".encode()


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    model = body.get("model", "gpt-4o-mini")
    if body.get("stream"):
        return StreamingResponse(_stream(model), media_type="text/event-stream")
    return {
        "id": "chatcmpl-mock0001",
        "object": "chat.completion",
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hello from the mock provider!"},
                "finish_reason": "stop",
            }
        ],
        "usage": USAGE,
    }


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8200)