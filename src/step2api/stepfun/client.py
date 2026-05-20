"""
StepFun client - main entry point combining auth, chat, and account management.
"""

import asyncio
import logging
import time
from typing import AsyncGenerator, Optional

from .auth import StepFunAuth
from .chat import StepFunChatSession
from ..core.pool import AccountInfo, pool
from ..core.config import config
from ..core.exceptions import AuthenticationError

logger = logging.getLogger(__name__)


class StepFunClient:
    """High-level client for StepFun web chat.

    Manages authentication (cookie-based) and chat sessions.
    """

    def __init__(self, account: AccountInfo):
        self.account = account
        self._auth: Optional[StepFunAuth] = None
        self._chat_session: Optional[StepFunChatSession] = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def close(self):
        if self._chat_session:
            await self._chat_session.close()
        if self._auth:
            await self._auth.close()

    async def ensure_authenticated(self) -> StepFunAuth:
        """Ensure the account has a valid session (cookies).

        Returns the auth instance with valid cookies.
        """
        self._auth = StepFunAuth(self.account.phone)

        # Try loading saved cookies
        if self.account.access_token:
            # access_token field now used to store serialized cookies
            try:
                import json as _json
                saved_cookies = _json.loads(self.account.access_token)
                self._auth.load_cookies(saved_cookies)
                if await self._auth.is_session_valid():
                    logger.debug(f"Session valid for {self.account.phone[-4:]}")
                    return self._auth
            except Exception:
                pass

        # Try refreshing the token (cookies)
        if self.account.refresh_token:
            # refresh_token field stores session cookies
            try:
                import json as _json
                saved_cookies = _json.loads(self.account.refresh_token)
                self._auth.load_cookies(saved_cookies)
                if await self._auth.refresh_token():
                    self._save_cookies()
                    logger.info(f"Session refreshed for {self.account.phone[-4:]}")
                    return self._auth
            except Exception:
                logger.warning("Session refresh failed, needs SMS login")

        # Check if cookies are still valid
        if await self._auth.is_session_valid():
            self._save_cookies()
            return self._auth

        # Need SMS login
        raise AuthenticationError(
            f"Account {self.account.phone[-4:]} needs SMS login. "
            "Use POST /admin/accounts/send-sms and /admin/accounts/login."
        )

    def _save_cookies(self):
        """Save auth cookies to account info."""
        if self._auth:
            import json as _json
            cookies = self._auth.export_cookies()
            self.account.access_token = _json.dumps(cookies)
            self.account.refresh_token = _json.dumps(cookies)
            self.account.token_expires_at = time.time() + 86400  # 24h

    async def send_sms_code(self) -> dict:
        """Send SMS verification code."""
        self._auth = StepFunAuth(self.account.phone)
        return await self._auth.send_sms_code()

    async def login_with_sms(self, code: str) -> dict:
        """Complete SMS login and save cookies."""
        self._auth = StepFunAuth(self.account.phone)
        result = await self._auth.login_with_sms(code)
        self._save_cookies()
        logger.info(f"Login successful for {self.account.phone[-4:]}")
        return result

    async def create_chat_session(self) -> StepFunChatSession:
        """Create or get a chat session for this account."""
        auth = await self.ensure_authenticated()

        if self._chat_session:
            await self._chat_session.close()

        self._chat_session = StepFunChatSession(
            account_name=self.account.name,
            cookies=auth.cookies,
        )

        return self._chat_session

    async def chat_completion_stream(
        self,
        messages: list,
        model: str = "step-auto",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[list] = None,
    ) -> AsyncGenerator[str, None]:
        """Send a chat completion request and yield OpenAI-format SSE chunks."""
        session = await self.create_chat_session()

        async for chunk in session.convert_to_openai_stream(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
        ):
            yield chunk

        # Auto-delete chat session if configured
        mode = config.auto_delete_mode
        if mode != "none" and session.chat_session_id:
            try:
                await session.delete_chat_session(session.chat_session_id)
            except Exception:
                pass


async def process_chat_completion(
    messages: list,
    model: str = "step-auto",
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    tools: Optional[list] = None,
    stream: bool = True,
    target_account: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """Process a chat completion request through the account pool.

    This is the main entry point for chat completion requests.
    It acquires an account from the pool, handles authentication,
    and streams the response.
    """
    account = await pool.acquire(target_account)
    try:
        client = StepFunClient(account)
        try:
            async for chunk in client.chat_completion_stream(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
            ):
                yield chunk
        finally:
            await client.close()
    finally:
        pool.release(account)
