from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from config.env_loader import load_env_file


class BaseLLMProvider:
    def generate(self, prompt: str) -> str | None:
        raise NotImplementedError


class OllamaProvider(BaseLLMProvider):
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


class ClaudeProvider(BaseLLMProvider):
    def __init__(self, timeout_seconds: int = 30) -> None:
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.model_name = os.environ.get("ANTHROPIC_MODEL")
        self.timeout_seconds = timeout_seconds

    def generate(self, prompt: str) -> str | None:
        if not self.api_key or not self.model_name:
            print("CLAUDE_PROVIDER_ERROR: missing ANTHROPIC_API_KEY or ANTHROPIC_MODEL")
            return None

        payload = {
            "model": self.model_name,
            "max_tokens": 600,
            "thinking": {"type": "disabled"},
            "system": (
                "You are AURA, a loyal virtual human companion. "
                "Be warm, natural, concise, emotionally present, and never robotic."
            ),
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            request = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=data,
                headers={
                    "content-type": "application/json",
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                },
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
            parsed: dict[str, Any] = json.loads(body)
            content = parsed.get("content", [])
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text = item.get("text")
                        if isinstance(text, str) and text.strip():
                            return text.strip()
            return None
        except urllib.error.HTTPError as err:
            error_body = err.read().decode("utf-8", errors="replace")
            print(f"CLAUDE_PROVIDER_ERROR: HTTP {err.code} {error_body}")
            return None
        except Exception as exc:
            print(f"CLAUDE_PROVIDER_ERROR: {exc}")
            return None


class GeminiProvider(BaseLLMProvider):
    def generate(self, prompt: str) -> str | None:
        return None


class GroqProvider(BaseLLMProvider):
    def generate(self, prompt: str) -> str | None:
        return None


class LLMProvider:
    def __init__(
        self,
        provider_name: str | None = None,
        timeout_seconds: int = 20,
    ) -> None:
        load_env_file()
        selected = provider_name or os.environ.get("AURA_BRAIN_PROVIDER") or "local"
        selected = selected.lower()

        if selected == "claude":
            self.provider: BaseLLMProvider | None = ClaudeProvider(timeout_seconds=timeout_seconds)
        elif selected == "ollama":
            self.provider = OllamaProvider(timeout_seconds=timeout_seconds)
        elif selected == "gemini":
            self.provider = GeminiProvider()
        elif selected == "groq":
            self.provider = GroqProvider()
        else:
            self.provider = None

    def generate(self, prompt: str) -> str | None:
        if self.provider is None:
            return None
        return self.provider.generate(prompt)
