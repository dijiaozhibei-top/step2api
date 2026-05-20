"""
StepFun authentication module.

Handles SMS-based phone login and cookie-based session management.
The StepFun web app uses HTTP cookies for authentication after login.
"""

import json
import logging
import time
from typing import Optional

import httpx

from ..core.exceptions import AuthenticationError

logger = logging.getLogger(__name__)

BASE_URL = "https://www.stepfun.com"
PASSPORT_BASE = f"{BASE_URL}/passport"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/",
}


class StepFunAuth:
    """Handles StepFun account authentication (phone/SMS login).

    Uses httpx.AsyncClient to persist cookies across requests.
    """

    def __init__(self, phone: str):
        self.phone = phone
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers=DEFAULT_HEADERS.copy(),
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def cookies(self) -> dict:
        """Get current cookies as a dict (for sharing with chat module)."""
        if self._client:
            return dict(self._client.cookies)
        return {}

    def export_cookies(self) -> dict:
        """Export cookies as a dict of {name: value}."""
        return {k: v for k, v in self.cookies.items()}

    def load_cookies(self, cookies: dict):
        """Load cookies into the client."""
        client = self._get_client()
        for name, value in cookies.items():
            client.cookies.set(name, value, domain="stepfun.com")

    async def _post(self, path: str, data: dict) -> dict:
        """Send a POST request to the passport service."""
        url = f"{PASSPORT_BASE}/{path}"
        headers = {"Content-Type": "application/json"}
        client = self._get_client()
        response = await client.post(url, json=data, headers=headers)
        if response.status_code >= 400:
            try:
                error_data = response.json()
                msg = error_data.get("message", response.text)
            except Exception:
                msg = response.text
            raise AuthenticationError(
                f"Auth request failed ({response.status_code}): {msg}"
            )
        return response.json()

    async def _api_post(self, path: str, data: dict) -> dict:
        """Send a POST request to the main API."""
        url = f"{BASE_URL}/api/{path}"
        headers = {"Content-Type": "application/json"}
        client = self._get_client()
        response = await client.post(url, json=data, headers=headers)
        if response.status_code == 401:
            raise AuthenticationError("Session expired, please re-login")
        if response.status_code >= 400:
            try:
                error_data = response.json()
                msg = error_data.get("message", response.text)
            except Exception:
                msg = response.text
            raise AuthenticationError(
                f"API request failed ({response.status_code}): {msg}"
            )
        return response.json()

    async def register_device(self) -> dict:
        """Register device to get a device ID."""
        return await self._post(
            "proto.api.passport.v1.PassportService/RegisterDevice",
            {"platform": "web"},
        )

    async def list_supported_region(self) -> dict:
        """List supported regions for phone login."""
        return await self._post(
            "proto.api.passport.v1.PassportService/ListSupportedRegion",
            {},
        )

    async def oauth_state(self) -> dict:
        """Get OAuth state for WeChat/other login methods."""
        return await self._post(
            "proto.api.passport.v1.PassportService/OAuthState",
            {},
        )

    async def send_sms_code(self) -> dict:
        """Send SMS verification code to the phone number."""
        return await self._post(
            "proto.api.passport.v1.PassportService/SendSmsCode",
            {"phone": self.phone},
        )

    async def login_with_sms(self, code: str) -> dict:
        """Login with phone number and SMS code.

        After successful login, cookies are set on the client.
        Returns the login response data.
        """
        result = await self._post(
            "proto.api.passport.v1.PassportService/LoginBySmsCode",
            {"phone": self.phone, "code": code},
        )
        logger.info(f"Login successful for {self.phone[-4:]}")
        return result

    async def refresh_token(self) -> bool:
        """Attempt to refresh the session (uses cookies, not token).

        Returns True if refresh was successful.
        """
        try:
            # The web app calls RefreshToken with cookies
            result = await self._post(
                "proto.api.passport.v1.PassportService/RefreshToken",
                {},
            )
            logger.info(f"Session refreshed for {self.phone[-4:]}")
            return True
        except Exception as e:
            logger.warning(f"Session refresh failed: {e}")
            return False

    async def get_user_info(self) -> dict:
        """Get user information using current session cookies."""
        return await self._api_post(
            "user/proto.api.user.v1.UserService/GetUser",
            {},
        )

    async def is_session_valid(self) -> bool:
        """Check if the current session is valid."""
        try:
            await self.get_user_info()
            return True
        except AuthenticationError:
            return False
