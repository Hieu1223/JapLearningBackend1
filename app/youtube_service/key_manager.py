import os
import json
from pathlib import Path
from threading import Lock
from datetime import datetime, date

_STATE_FILE = Path(__file__).parent / ".key_state.json"
_lock = Lock()


def _load_keys() -> list[str]:
    raw = os.getenv("YOUTUBE_API_KEYS", "")
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    if not keys:
        raise RuntimeError("YOUTUBE_API_KEYS env var is not set or empty")
    return keys


def _load_state(num_keys: int) -> dict:
    try:
        if _STATE_FILE.exists():
            data = json.loads(_STATE_FILE.read_text())
            # Guard against key list changing size
            if len(data.get("exhausted", [])) != num_keys:
                raise ValueError("key count mismatch")
            return {
                "index": int(data.get("index", 0)) % num_keys,
                "exhausted": data["exhausted"],  # list of "YYYY-MM-DD" or null per key
            }
    except Exception:
        pass
    return {"index": 0, "exhausted": [None] * num_keys}


def _save_state(state: dict):
    _STATE_FILE.write_text(json.dumps(state))


def _is_exhausted(exhausted_on: str | None) -> bool:
    """A key is exhausted only for the calendar day it was marked (YouTube quota resets daily)."""
    if not exhausted_on:
        return False
    return exhausted_on == date.today().isoformat()


class KeyManager:
    def __init__(self):
        with _lock:
            self._keys = _load_keys()
            self._state = _load_state(len(self._keys))

    def get_current_key(self) -> str:
        with _lock:
            keys = self._keys
            state = self._state
            today = date.today().isoformat()

            # Clear stale exhaustion marks from previous days
            state["exhausted"] = [
                e if e == today else None for e in state["exhausted"]
            ]

            start = state["index"]
            for offset in range(len(keys)):
                idx = (start + offset) % len(keys)
                if not _is_exhausted(state["exhausted"][idx]):
                    state["index"] = idx
                    _save_state(state)
                    return keys[idx]

            raise RuntimeError("All YouTube API keys are exhausted for today. Quota resets at midnight PT.")

    def mark_exhausted(self, key: str):
        """Call this when a quota error is returned for the given key."""
        with _lock:
            try:
                idx = self._keys.index(key)
            except ValueError:
                return
            today = date.today().isoformat()
            self._state["exhausted"][idx] = today
            # Advance index to next available key
            self._state["index"] = (idx + 1) % len(self._keys)
            _save_state(self._state)

    def advance(self):
        """Advance to next key (called after each successful request for round-robin)."""
        with _lock:
            self._state["index"] = (self._state["index"] + 1) % len(self._keys)
            _save_state(self._state)


# Singleton — shared across all requests in the process
key_manager = KeyManager()