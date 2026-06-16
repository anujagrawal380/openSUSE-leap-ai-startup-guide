"""
Persistent prompt-response cache for the assistant.

This cache stores completed assistant responses by a deterministic key so a
repeated prompt can be answered without running retrieval or generation again.
"""

import hashlib
import json
import os
import re
import time
from dataclasses import asdict
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from opensuse_ai.assistant import AssistantResponse


def normalize_prompt(prompt: str) -> str:
    """Normalize whitespace while preserving the prompt's wording and casing."""
    return re.sub(r"\s+", " ", prompt).strip()


class PromptResponseCache:
    """Small JSON-backed cache for assistant responses."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._data: dict[str, Any] | None = None

    def get(
        self,
        prompt: str,
        *,
        system_context: str = "",
    ) -> dict | None:
        """Return a cached response payload for this prompt, if present."""
        entry = self._entries().get(self._key(prompt, system_context=system_context))
        if not entry:
            return None
        return entry.get("response")

    def set(
        self,
        prompt: str,
        response: "AssistantResponse",
        *,
        system_context: str = "",
    ) -> None:
        """Store a response payload for future identical prompts."""
        data = self._load()
        key = self._key(prompt, system_context=system_context)
        data.setdefault("entries", {})[key] = {
            "prompt": normalize_prompt(prompt),
            "system_context_hash": self._hash(system_context),
            "created_at": time.time(),
            "response": asdict(response),
        }
        self._write(data)

    def _entries(self) -> dict:
        return self._load().setdefault("entries", {})

    def _load(self) -> dict:
        if self._data is not None:
            return self._data
        if not self.path.exists():
            self._data = {"version": 1, "entries": {}}
            return self._data

        try:
            with open(self.path) as f:
                loaded = json.load(f)
        except (OSError, json.JSONDecodeError):
            loaded = {"version": 1, "entries": {}}
        if not isinstance(loaded, dict):
            loaded = {"version": 1, "entries": {}}
        loaded.setdefault("version", 1)
        loaded.setdefault("entries", {})
        self._data = loaded
        return self._data

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            "w",
            dir=self.path.parent,
            delete=False,
        ) as tmp:
            json.dump(data, tmp, indent=2, sort_keys=True)
            tmp.write("\n")
            tmp_path = tmp.name
        os.replace(tmp_path, self.path)
        self._data = data

    def _key(self, prompt: str, *, system_context: str) -> str:
        parts = [
            normalize_prompt(prompt),
            self._hash(system_context),
        ]
        return self._hash("\n---\n".join(parts))

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
