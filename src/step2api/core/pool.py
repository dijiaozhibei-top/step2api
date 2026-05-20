"""
Account pool and concurrency control.
"""

import asyncio
import time
import threading
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AccountInfo:
    """Represents a StepFun account with its state."""

    phone: str
    name: str = ""
    remark: str = ""

    # Auth state (stores serialized cookies JSON instead of JWT tokens)
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expires_at: float = 0.0

    # Concurrency control
    in_flight: int = 0
    last_used: float = 0.0

    # Session/chat state
    session_id: Optional[str] = None

    # Stats
    total_requests: int = 0
    total_errors: int = 0

    @property
    def is_authenticated(self) -> bool:
        """Check if the account has saved session cookies and they haven't expired."""
        return bool(self.access_token) and (
            self.token_expires_at == 0.0 or time.time() < self.token_expires_at
        )

    @property
    def is_available(self) -> bool:
        from .config import config
        return self.in_flight < config.account_max_inflight


class AccountPool:
    """Manages multiple StepFun accounts with concurrency control."""

    def __init__(self):
        self._accounts: list[AccountInfo] = []
        self._lock = threading.Lock()
        self._queue: list[asyncio.Event] = []

    def load_accounts(self, accounts_config: list):
        """Load accounts from configuration."""
        with self._lock:
            self._accounts = []
            for acc in accounts_config:
                self._accounts.append(AccountInfo(
                    phone=acc.get("phone", ""),
                    name=acc.get("name", ""),
                    remark=acc.get("remark", ""),
                ))
        logger.info(f"Loaded {len(self._accounts)} accounts")

    async def acquire(self, target_account: Optional[str] = None) -> AccountInfo:
        """Acquire an available account slot. Blocks if all are busy."""
        from .config import config

        while True:
            with self._lock:
                candidates = self._accounts
                if target_account:
                    candidates = [a for a in self._accounts
                                  if a.phone == target_account or a.name == target_account]
                    if not candidates:
                        raise ValueError(f"Account {target_account} not found")

                # Prefer already authenticated accounts with lowest in_flight
                available = [a for a in candidates if a.is_available]
                if available:
                    available.sort(key=lambda a: a.in_flight)
                    account = available[0]
                    account.in_flight += 1
                    account.total_requests += 1
                    account.last_used = time.time()
                    return account

                # Check if queue is full
                total_inflight = sum(a.in_flight for a in self._accounts)
                queue_size = len(self._queue)
                max_queue = config.account_max_queue
                if queue_size + total_inflight >= max_queue * len(self._accounts):
                    from .exceptions import TooManyRequestsError
                    raise TooManyRequestsError("All accounts busy, queue full")

            # Wait for a slot
            event = asyncio.Event()
            self._queue.append(event)
            try:
                await asyncio.wait_for(event.wait(), timeout=60.0)
            except asyncio.TimeoutError:
                self._queue.remove(event)
                from .exceptions import TooManyRequestsError
                raise TooManyRequestsError("Queue timeout, all accounts still busy")

    def release(self, account: AccountInfo):
        """Release an account slot."""
        with self._lock:
            account.in_flight = max(0, account.in_flight - 1)
            if self._queue:
                event = self._queue.pop(0)
                event.set()

    def get_status(self) -> dict:
        """Get current pool status."""
        with self._lock:
            accounts_status = []
            for a in self._accounts:
                accounts_status.append({
                    "phone": a.phone[-4:].rjust(len(a.phone), "*"),
                    "name": a.name,
                    "in_flight": a.in_flight,
                    "authenticated": a.is_authenticated,
                    "total_requests": a.total_requests,
                    "total_errors": a.total_errors,
                })
            return {
                "total_accounts": len(self._accounts),
                "queue_size": len(self._queue),
                "accounts": accounts_status,
            }


# Global account pool
pool = AccountPool()
