from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class LLMProvider:
    def __init__(
        self,
        model_name: str = "llama3.1",
        ollama_url: str = "http://localhost:11434/api/generate",
        timeout_seconds: int = 20,
    ) -> None:
        self.model_name = model_name
        self.ollama_url = ollama_url
        self.timeout_seconds = timeout_seconds

    def generate(self, prompt: str) -> str | None:
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            request = urllib.request.Request(
                self.ollama_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
            parsed: dict[str, Any] = json.loads(body)
            text = parsed.get("response")
            if isinstance(text, str) and text.strip():
                return text.strip()
            return None
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
            return None
