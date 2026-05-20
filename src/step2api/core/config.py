"""
Core configuration and state management.
"""

import json
import os
import threading
from pathlib import Path
from typing import Optional

# Default config path
DEFAULT_CONFIG_PATH = Path(os.environ.get("STEP2API_CONFIG_PATH", "config.json"))


class Config:
    """Global configuration loaded from config.json."""

    def __init__(self, config_path: Optional[Path] = None):
        self._path = config_path or DEFAULT_CONFIG_PATH
        self._lock = threading.RLock()
        self._data: dict = {}
        self.load()

    def load(self):
        """Load configuration from file or environment."""
        env_config = os.environ.get("STEP2API_CONFIG_JSON", "")
        if env_config:
            import base64
            try:
                decoded = base64.b64decode(env_config).decode("utf-8")
                self._data = json.loads(decoded)
                return
            except Exception:
                pass
            try:
                self._data = json.loads(env_config)
                return
            except json.JSONDecodeError:
                pass

        if self._path.exists():
            with open(self._path, "r", encoding="utf-8") as f:
                self._data = json.load(f)

    def save(self):
        """Save configuration to file."""
        with self._lock:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)

    @property
    def host(self) -> str:
        return os.environ.get("STEP2API_HOST", self._data.get("host", "127.0.0.1"))

    @property
    def port(self) -> int:
        return int(os.environ.get("STEP2API_PORT", self._data.get("port", 5001)))

    @property
    def keys(self) -> list:
        env_key = os.environ.get("STEP2API_ADMIN_KEY", "")
        if env_key:
            return [env_key]
        return self._data.get("keys", []) or [ak.get("key", "") for ak in self._data.get("api_keys", [])]

    @property
    def api_keys(self) -> list:
        return self._data.get("api_keys", [{"key": k, "name": "default", "remark": ""} for k in self.keys])

    @property
    def accounts(self) -> list:
        accounts_json = os.environ.get("STEP2API_ACCOUNTS", "")
        if accounts_json:
            return json.loads(accounts_json)
        return self._data.get("accounts", [])

    @property
    def model_aliases(self) -> dict:
        return self._data.get("model_aliases", {})

    @property
    def runtime(self) -> dict:
        return self._data.get("runtime", {
            "account_max_inflight": 2,
            "account_max_queue": 4,
            "token_refresh_interval": 600,
        })

    @property
    def account_max_inflight(self) -> int:
        return int(os.environ.get("STEP2API_ACCOUNT_MAX_INFLIGHT", self.runtime.get("account_max_inflight", 2)))

    @property
    def account_max_queue(self) -> int:
        return int(os.environ.get("STEP2API_ACCOUNT_MAX_QUEUE", self.runtime.get("account_max_queue", 4)))

    @property
    def auto_delete_mode(self) -> str:
        return self._data.get("auto_delete", {}).get("mode", "none")

    def get_data(self) -> dict:
        return self._data.copy()

    def update(self, data: dict):
        with self._lock:
            self._data.update(data)
            self.save()

    def resolve_model(self, model_name: str) -> str:
        """Resolve model alias to actual model name."""
        return self.model_aliases.get(model_name, model_name)


# Global config instance
config = Config()
