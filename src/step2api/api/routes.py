"""
OpenAI-compatible API routes using FastAPI.
"""

import json
import logging
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from ..core.config import config
from ..core.exceptions import (
    AuthenticationError,
    TooManyRequestsError,
    InvalidRequestError,
    Step2APIError,
)
from ..core.pool import pool
from ..stepfun.client import process_chat_completion

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["OpenAI Compatible"])


# --- Pydantic Models ---

class Message(BaseModel):
    role: str
    content: str | list


class ChatCompletionRequest(BaseModel):
    model: str = "step-3.5-flash"
    messages: list[Message]
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = None
    stream: bool = False
    tools: Optional[list] = None
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    n: int = Field(default=1, ge=1, le=5)
    stop: Optional[str | list[str]] = None
    user: Optional[str] = None


class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str = "stepfun"


# --- Auth Middleware ---

def verify_api_key(request: Request) -> Optional[str]:
    """Verify the API key from the request.

    Returns the account name if a specific account is targeted, None otherwise.
    """
    auth_header = request.headers.get("Authorization", "")
    api_key = request.headers.get("x-api-key", "")

    key = ""
    if auth_header.startswith("Bearer "):
        key = auth_header[7:]
    elif api_key:
        key = api_key

    if not key:
        return None

    # Check if it's a configured API key
    valid_keys = [k.get("key", "") for k in config.api_keys]
    valid_keys.extend(config.keys)

    if key in valid_keys:
        return None  # Valid API key, use pool

    # Check if it's a direct token (for passthrough mode)
    # Any non-configured key is treated as a direct StepFun token
    return None


async def check_auth(request: Request):
    """Check authentication and raise if invalid."""
    auth_header = request.headers.get("Authorization", "")
    api_key = request.headers.get("x-api-key", "")

    key = ""
    if auth_header.startswith("Bearer "):
        key = auth_header[7:]
    elif api_key:
        key = api_key

    if not key:
        raise AuthenticationError("Missing API key. Use Bearer token or x-api-key header.")

    valid_keys = [k.get("key", "") for k in config.api_keys]
    valid_keys.extend(config.keys)

    if key not in valid_keys:
        raise AuthenticationError("Invalid API key.")


# --- Routes ---

@router.get("/models")
async def list_models():
    """List available models."""
    models = [
        ModelInfo(
            id="step-3.5-flash",
            created=1710100000,
        ),
        ModelInfo(
            id="step-2-mini",
            created=1710100000,
        ),
        ModelInfo(
            id="step-1v-8k",
            created=1710100000,
        ),
        ModelInfo(
            id="step-1-8k",
            created=1710100000,
        ),
    ]

    # Add aliases
    for alias in config.model_aliases:
        models.append(ModelInfo(
            id=alias,
            created=1710100000,
        ))

    return JSONResponse({
        "object": "list",
        "data": [m.model_dump() for m in models],
    })


@router.get("/models/{model_id}")
async def retrieve_model(model_id: str):
    """Retrieve a specific model."""
    resolved = config.resolve_model(model_id)
    return JSONResponse({
        "id": model_id,
        "object": "model",
        "created": 1710100000,
        "owned_by": "stepfun",
    })


@router.post("/chat/completions")
async def chat_completions(request: Request, body: ChatCompletionRequest):
    """Create a chat completion (OpenAI-compatible)."""
    await check_auth(request)

    # Get target account from header
    target_account = request.headers.get("x-step2-target-account")

    # Resolve model alias
    resolved_model = config.resolve_model(body.model)

    # Convert messages to list of dicts
    messages = [m.model_dump() for m in body.messages]

    # Inject thinking prompt if configured
    thinking_config = config._data.get("thinking_injection", {})
    if thinking_config.get("enabled", True) and messages:
        last_user_idx = -1
        for i in range(len(messages) - 1, -1, -1):
            if messages[i]["role"] == "user":
                last_user_idx = i
                break
        if last_user_idx >= 0:
            prompt = thinking_config.get("prompt", "")
            if prompt:
                content = messages[last_user_idx]["content"]
                if isinstance(content, str):
                    messages[last_user_idx]["content"] = f"{prompt}\n\n{content}"

    if body.stream:
        return StreamingResponse(
            _stream_response(
                messages=messages,
                model=resolved_model,
                temperature=body.temperature,
                max_tokens=body.max_tokens,
                tools=body.tools,
                target_account=target_account,
                request_model=body.model,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        # Non-streaming: collect all chunks and return single response
        request_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"
        created = int(time.time())
        content = ""
        finish_reason = "stop"

        try:
            async for chunk in process_chat_completion(
                messages=messages,
                model=resolved_model,
                temperature=body.temperature,
                max_tokens=body.max_tokens,
                tools=body.tools,
                stream=True,
                target_account=target_account,
            ):
                if chunk.startswith("data: ") and not chunk.startswith("data: [DONE]"):
                    try:
                        data = json.loads(chunk[6:].strip())
                        delta = (
                            data.get("choices", [{}])[0]
                            .get("delta", {})
                            .get("content", "")
                        )
                        content += delta
                        if data.get("choices", [{}])[0].get("finish_reason"):
                            finish_reason = (
                                data["choices"][0]["finish_reason"] or "stop"
                            )
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            logger.error(f"Chat completion error: {e}")
            raise Step2APIError(str(e))

        return JSONResponse({
            "id": request_id,
            "object": "chat.completion",
            "created": created,
            "model": body.model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                },
                "finish_reason": finish_reason,
            }],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        })


async def _stream_response(
    messages: list,
    model: str,
    temperature: float,
    max_tokens: Optional[int],
    tools: Optional[list],
    target_account: Optional[str],
    request_model: str,
):
    """Generate SSE stream response."""
    try:
        async for chunk in process_chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            stream=True,
            target_account=target_account,
        ):
            yield chunk
    except TooManyRequestsError as e:
        yield f"data: {{\"error\":{{\"message\":\"{str(e)}\",\"type\":\"rate_limit_error\"}}}}\n\n"
        yield "data: [DONE]\n\n"
    except AuthenticationError as e:
        yield f"data: {{\"error\":{{\"message\":\"{str(e)}\",\"type\":\"authentication_error\"}}}}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        logger.error(f"Stream error: {e}")
        yield f"data: {{\"error\":{{\"message\":\"{str(e)}\",\"type\":\"server_error\"}}}}\n\n"
        yield "data: [DONE]\n\n"


# --- Admin routes ---

admin_router = APIRouter(prefix="/admin", tags=["Admin"])


@admin_router.get("/queue/status")
async def queue_status(request: Request):
    """Get account pool status."""
    await check_auth(request)
    return JSONResponse(pool.get_status())


@admin_router.get("/accounts")
async def list_accounts(request: Request):
    """List configured accounts."""
    await check_auth(request)
    return JSONResponse({
        "accounts": [{
            "phone": a.phone[-4:].rjust(len(a.phone), "*"),
            "name": a.name,
            "remark": a.remark,
            "authenticated": a.is_authenticated,
        } for a in pool._accounts],
    })


@admin_router.post("/accounts/send-sms")
async def send_sms(request: Request):
    """Send SMS code for an account."""
    await check_auth(request)
    body = await request.json()
    phone = body.get("phone", "")

    from ..stepfun.client import StepFunClient
    for acc in pool._accounts:
        if acc.phone == phone:
            client = StepFunClient(acc)
            try:
                result = await client.send_sms_code()
                return JSONResponse({"status": "ok", "result": result})
            finally:
                await client.close()

    raise InvalidRequestError(f"Account {phone} not found")


@admin_router.post("/accounts/login")
async def login_account(request: Request):
    """Complete SMS login for an account."""
    await check_auth(request)
    body = await request.json()
    phone = body.get("phone", "")
    code = body.get("code", "")

    from ..stepfun.client import StepFunClient
    for acc in pool._accounts:
        if acc.phone == phone:
            client = StepFunClient(acc)
            try:
                result = await client.login_with_sms(code)
                return JSONResponse({"status": "ok", "result": result})
            finally:
                await client.close()

    raise InvalidRequestError(f"Account {phone} not found")


# --- Health routes ---

health_router = APIRouter()


@health_router.get("/healthz")
async def healthz():
    """Liveness probe."""
    return {"status": "ok"}


@health_router.get("/readyz")
async def readyz():
    """Readiness probe."""
    return {"status": "ok"}
