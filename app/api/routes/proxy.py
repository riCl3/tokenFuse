import asyncio
import json
from collections.abc import AsyncGenerator

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.deps import AuthContext, get_current_project
from app.core.config import get_settings
from app.core.pricing import estimate_cost_usd
from app.schemas.proxy import ChatCompletionRequest
from app.services import budget_service, provider_client

settings = get_settings()

router = APIRouter(prefix="/v1/chat", tags=["proxy"])

WARN_HEADER = "X-TokenFuse-Warning"

# Strong references to background "tap" tasks. The event loop only holds weak
# references to tasks, so without this a tap could be garbage-collected
# mid-drain (and never commit usage). Done callbacks drop the reference.
_active_taps: set[asyncio.Task] = set()


def _track(task: asyncio.Task) -> None:
    _active_taps.add(task)
    task.add_done_callback(_active_taps.discard)


@router.post("/completions")
async def chat_completions(
    payload: ChatCompletionRequest,
    auth: AuthContext = Depends(get_current_project),
) -> Response:
    budget_units = budget_service.window_budget_units(
        float(auth.project.monthly_budget_usd), settings.budget_window_seconds
    )
    status_result = await budget_service.check_budget(
        auth.project.id, budget_units, auth.project.warn_pct
    )

    response_headers = {}
    if status_result.status == "exceeded":
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "budget_exceeded",
                "used_units": status_result.used_units,
                "budget_units": status_result.budget_units,
            },
        )
    if status_result.status == "warn":
        response_headers[WARN_HEADER] = (
            f"budget at {status_result.used_units} of {status_result.budget_units} units"
        )

    body = payload.model_dump(exclude={"provider"})

    if body.get("stream"):
        # Ask the provider to append a final chunk carrying the cumulative
        # usage totals (OpenAI-compatible providers honor stream_options).
        body["stream_options"] = {"include_usage": True}
        return StreamingResponse(
            _stream_proxy(body, payload.provider, auth),
            media_type="text/event-stream",
            headers=response_headers,
        )

    try:
        result = await provider_client.forward_chat_completion(body, payload.provider)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream provider error ({exc.response.status_code})",
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Upstream provider unreachable",
        )

    if result.usage is not None:
        cost = estimate_cost_usd(
            payload.model, result.usage.prompt_tokens, result.usage.completion_tokens
        )
        await budget_service.record_usage(auth.project.id, cost)
        # TODO(Phase 8): persist a UsageEvent row to Postgres for the dashboard.

    return JSONResponse(content=result.data, headers=response_headers)


def _parse_usage_line(line: bytes) -> dict | None:
    """Return the `usage` object from one SSE `data: {...}` line, if present."""
    line = line.strip()
    if not line.startswith(b"data:"):
        return None
    data = line[len(b"data:"):].strip()
    if data == b"[DONE]":
        return None
    try:
        obj = json.loads(data)
    except json.JSONDecodeError:
        return None
    return obj.get("usage")


async def _tap_stream(
    body: dict,
    provider: str,
    auth: AuthContext,
    queue: asyncio.Queue[bytes | None],
) -> None:
    """Own the upstream stream: push every chunk into the queue, then commit usage.

    This runs as an INDEPENDENT background task (created with create_task), not
    inside the generator, so a client disconnect cancelling the generator does
    NOT cancel this task. It keeps draining the provider to the end, picks up
    the final usage chunk, and records the spend even though the client is gone.
    """
    usage = None
    buffer = b""
    try:
        async for chunk in provider_client.stream_chat_completion(body, provider):
            await queue.put(chunk)
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                parsed = _parse_usage_line(line)
                if parsed:
                    usage = parsed
    except httpx.HTTPStatusError as exc:
        await queue.put(
            b"data: " + json.dumps({"error": f"upstream_status_{exc.response.status_code}"}).encode() + b"\n\n"
        )
    except httpx.RequestError:
        await queue.put(b'data: {"error": "upstream_unreachable"}\n\n')
    finally:
        # Sentinel: the generator can stop pulling. Committed afterwards so the
        # spend is recorded regardless of whether the generator got this far.
        await queue.put(None)
        if usage:
            cost = estimate_cost_usd(
                body["model"], usage["prompt_tokens"], usage["completion_tokens"]
            )
            await budget_service.record_usage(auth.project.id, cost)


async def _stream_proxy(
    body: dict, provider: str, auth: AuthContext
) -> AsyncGenerator[bytes, None]:
    """Forward streamed chunks immediately; a background tap commits usage.

    The generator only relays what the tap task puts on the queue, so it adds
    no latency. If the client disconnects mid-stream, Starlette cancels this
    generator; the finally awaits the tap (via asyncio.shield) only to see the
    cancellation - the tracked tap task itself keeps draining and commits the
    spend in the background. Without this, cancelling the client would cancel
    the upstream read too, discarding the usage chunk - a budget loophole.
    """
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    tap = asyncio.create_task(_tap_stream(body, provider, auth, queue))
    _track(tap)
    try:
        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            yield chunk
    finally:
        if not tap.done():
            try:
                await asyncio.shield(tap)
            except asyncio.CancelledError:
                # Client disconnected. Re-raise; the tap keeps running and will
                # still record usage (it is tracked in _active_taps).
                raise