"""
StepFun chat session and completion module.

Handles:
- Creating/restoring chat sessions via CreateChatSession
- Sending messages via ChatStream (Connect protocol)
- Parsing streaming Connect events (reasoningEvent, textEvent, etc.)
- Converting StepFun's internal API format to OpenAI-compatible format
"""

import json
import logging
import struct
import uuid
import time
from typing import AsyncGenerator, Optional

import httpx

from ..core.config import config
from ..core.exceptions import UpstreamError, AuthenticationError

logger = logging.getLogger(__name__)

BASE_URL = "https://www.stepfun.com"
API_BASE = f"{BASE_URL}/api"

# Connect protocol constants
CONNECT_FLAG_NONE = 0x00
CONNECT_FLAG_END_STREAM = 0x02


def encode_connect_message(data: dict) -> bytes:
    """Encode a JSON message in Connect protocol format (length-prefixed)."""
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    header = struct.pack(">BI", CONNECT_FLAG_NONE, len(body))
    return header + body


def encode_connect_end_stream() -> bytes:
    """Encode the Connect end-of-stream marker."""
    body = b"{}"
    header = struct.pack(">BI", CONNECT_FLAG_END_STREAM, len(body))
    return header + body


async def read_connect_stream(response: httpx.Response) -> AsyncGenerator[dict, None]:
    """Read Connect streaming response, yielding parsed JSON events."""
    buffer = b""
    async for chunk in response.aiter_bytes():
        buffer += chunk
        while len(buffer) >= 5:
            flags = buffer[0]
            msg_len = struct.unpack(">I", buffer[1:5])[0]
            if len(buffer) < 5 + msg_len:
                break  # Incomplete message
            body = buffer[5:5 + msg_len]
            buffer = buffer[5 + msg_len:]

            if flags & CONNECT_FLAG_END_STREAM:
                return  # End of stream

            try:
                event = json.loads(body.decode("utf-8"))
                yield event
            except json.JSONDecodeError:
                logger.debug(f"Failed to parse Connect message: {body[:200]}")


class StepFunChatSession:
    """Manages a single chat session on stepfun.com using Connect protocol."""

    def __init__(self, account_name: str = "", cookies: dict | None = None):
        self.account_name = account_name
        self.chat_session_id: Optional[str] = None
        self.chat_id: Optional[str] = None
        self._client = httpx.AsyncClient(
            timeout=120.0,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                "Origin": BASE_URL,
                "Referer": f"{BASE_URL}/",
            },
            cookies=cookies or {},
        )

    async def close(self):
        await self._client.aclose()

    async def _connect_post(self, path: str, data: dict) -> dict:
        """Send a Connect unary POST request (request & response use Connect format)."""
        url = f"{API_BASE}/{path}"
        body = encode_connect_message(data)
        headers = {
            "Content-Type": "application/connect+json",
            "connect-protocol-version": "1",
        }
        response = await self._client.post(url, content=body, headers=headers)
        if response.status_code == 401:
            raise AuthenticationError("Access token expired or invalid")
        if response.status_code >= 400:
            try:
                error_data = response.json()
                msg = error_data.get("message", response.text)
            except Exception:
                msg = response.text
            raise UpstreamError(f"API request failed ({response.status_code}): {msg}")

        # Parse Connect response (unary: single length-prefixed message)
        raw = response.content
        if len(raw) >= 5:
            flags = raw[0]
            msg_len = struct.unpack(">I", raw[1:5])[0]
            body = raw[5:5 + msg_len]
            if flags & CONNECT_FLAG_END_STREAM:
                # End-stream flag may be set with final message
                pass
            return json.loads(body.decode("utf-8"))
        return response.json()  # Fallback

    async def _connect_stream_post(self, path: str, data: dict) -> httpx.Response:
        """Send a Connect streaming POST request."""
        url = f"{API_BASE}/{path}"
        body = encode_connect_message(data)
        headers = {
            "Content-Type": "application/connect+json",
            "connect-protocol-version": "1",
            "oasis-appid": "10200",
            "oasis-platform": "web",
            "oasis-language": "zh",
            "canary": "false",
        }
        request = self._client.build_request("POST", url, content=body, headers=headers)
        response = await self._client.send(request, stream=True)
        if response.status_code == 401:
            raise AuthenticationError("Access token expired or invalid")
        if response.status_code >= 400:
            try:
                error_data = response.json()
                msg = error_data.get("message", response.text)
            except Exception:
                msg = response.text
            raise UpstreamError(f"API request failed ({response.status_code}): {msg}")
        return response

    async def get_chat_config(self) -> dict:
        """Get chat configuration (models, studios, etc.)."""
        return await self._connect_post(
            "agent/capy.agent.v1.AgentService/GetChatConfig",
            {},
        )

    async def list_studios(self) -> dict:
        """List available studios (model categories)."""
        return await self._connect_post(
            "agent/capy.agent.v1.AgentService/ListStudios",
            {},
        )

    async def create_chat_session(self) -> str:
        """Create a new chat session and return the chatSessionId."""
        result = await self._connect_post(
            "agent/capy.agent.v1.AgentService/CreateChatSession",
            {},
        )
        session = result.get("chatSession", {})
        self.chat_session_id = session.get("chatSessionId", "")
        self.chat_id = session.get("chatId", "")
        logger.info(
            f"Created chat session {self.chat_session_id} "
            f"(chat {self.chat_id})"
        )
        return self.chat_session_id

    async def delete_chat_session(self, chat_session_id: Optional[str] = None):
        """Delete a chat session."""
        sid = chat_session_id or self.chat_session_id
        if not sid:
            return
        try:
            await self._connect_post(
                "agent/capy.agent.v1.AgentService/DeleteChatSession",
                {"chatSessionId": sid},
            )
        except Exception:
            logger.warning(f"Failed to delete chat session {sid}")

    async def chat_stream(
        self,
        content: str,
        model: str = "step-auto",
        enable_reasoning: bool = True,
        chat_session_id: Optional[str] = None,
    ) -> AsyncGenerator[dict, None]:
        """Send a chat message and yield parsed Connect stream events.

        Yields events like:
          {"data": {"event": {"startEvent": {"messageId": "..."}}}}
          {"data": {"event": {"reasoningEvent": {"text": "..."}}}}
          {"data": {"event": {"textEvent": {"text": "..."}}}}
          {"data": {"event": {"messageDoneEvent": {}}}}
          {"data": {"event": {"doneEvent": {}}}}
        """
        sid = chat_session_id or self.chat_session_id
        if not sid:
            sid = await self.create_chat_session()
            self.chat_session_id = sid

        payload = {
            "message": {
                "chatSessionId": sid,
                "content": {
                    "userMessage": {
                        "qa": {
                            "content": content,
                        }
                    }
                },
            },
            "config": {
                "model": model,
                "enableReasoning": enable_reasoning,
            },
        }

        response = await self._connect_stream_post(
            "agent/capy.agent.v1.AgentService/ChatStream",
            payload,
        )

        async for event in read_connect_stream(response):
            yield event

    async def convert_to_openai_stream(
        self,
        messages: list,
        model: str = "step-auto",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[list] = None,
        chat_session_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Send messages and convert StepFun Connect stream to OpenAI SSE format.

        Handles the conversion from StepFun's internal streaming events
        (reasoningEvent, textEvent, etc.) to OpenAI-compatible SSE chunks.

        Yields SSE strings like:
            data: {"id":"...","object":"chat.completion.chunk","choices":[...]}\n\n
        """
        # Extract the last user message content
        last_user_content = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                c = msg.get("content", "")
                if isinstance(c, list):
                    # Handle multimodal content - extract text parts
                    text_parts = [
                        p.get("text", "")
                        for p in c
                        if isinstance(p, dict) and p.get("type") == "text"
                    ]
                    last_user_content = "\n".join(text_parts)
                else:
                    last_user_content = str(c)
                break

        if not last_user_content:
            raise UpstreamError("No user message found in the conversation")

        # Optionally inject system prompt as prefix
        thinking_config = config._data.get("thinking_injection", {})
        if thinking_config.get("enabled", True):
            prompt = thinking_config.get("prompt", "")
            if prompt and not any(m.get("role") == "system" for m in messages):
                last_user_content = f"{prompt}\n\n{last_user_content}"

        request_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"
        created = int(time.time())
        model_resolved = config.resolve_model(model)

        # Send initial chunk with role
        yield (
            f'data: {{"id":"{request_id}","object":"chat.completion.chunk",'
            f'"created":{created},"model":"{model_resolved}","choices":'
            f'[{{"index":0,"delta":{{"role":"assistant","content":""}},'
            f'"finish_reason":null}}]}}\n\n'
        )

        finish_reason = None
        is_reasoning = False

        try:
            async for event in self.chat_stream(
                content=last_user_content,
                model=model_resolved,
                enable_reasoning=True,
                chat_session_id=chat_session_id,
            ):
                event_data = event.get("data", {}).get("event", {})
                event_type = next(iter(event_data.keys()), "") if event_data else ""

                if event_type == "textEvent":
                    if is_reasoning:
                        # End reasoning section
                        is_reasoning = False
                    text = event_data["textEvent"].get("text", "")
                    if text:
                        yield (
                            f'data: {{"id":"{request_id}",'
                            f'"object":"chat.completion.chunk",'
                            f'"created":{created},'
                            f'"model":"{model_resolved}",'
                            f'"choices":[{{"index":0,'
                            f'"delta":{{"content":{json.dumps(text, ensure_ascii=False)}}},'
                            f'"finish_reason":null}}]}}\n\n'
                        )

                elif event_type == "reasoningEvent":
                    # Optionally output reasoning_content (DeepSeek-style)
                    is_reasoning = True
                    reasoning_text = event_data["reasoningEvent"].get("text", "")
                    if reasoning_text:
                        yield (
                            f'data: {{"id":"{request_id}",'
                            f'"object":"chat.completion.chunk",'
                            f'"created":{created},'
                            f'"model":"{model_resolved}",'
                            f'"choices":[{{"index":0,'
                            f'"delta":{{"reasoning_content":'
                            f'{json.dumps(reasoning_text, ensure_ascii=False)}}},'
                            f'"finish_reason":null}}]}}\n\n'
                        )

                elif event_type == "messageDoneEvent":
                    finish_reason = "stop"

                elif event_type == "doneEvent":
                    finish_reason = "stop"
                    break

                elif event_type == "startEvent":
                    # Stream started - could log messageId
                    pass

                elif event_type == "messageEvent":
                    # Message metadata received
                    pass

                elif event_type == "pipelineEvent":
                    # Pipeline state change (reasoning start/end, etc.)
                    pipeline = event_data["pipelineEvent"]
                    if pipeline.get("action") == "EVENT_ACTION_END":
                        if pipeline.get("type") == "EVENT_TYPE_REASONING":
                            is_reasoning = False

                elif event_type == "heartBeatEvent":
                    # Keepalive - ignore
                    pass

        except Exception as e:
            logger.error(f"Stream error: {e}")
            finish_reason = "error"

        # Send final chunk
        final_reason = finish_reason or "stop"
        yield (
            f'data: {{"id":"{request_id}","object":"chat.completion.chunk",'
            f'"created":{created},"model":"{model_resolved}","choices":'
            f'[{{"index":0,"delta":{{}},"finish_reason":"{final_reason}"}}]}}\n\n'
        )
        yield "data: [DONE]\n\n"
