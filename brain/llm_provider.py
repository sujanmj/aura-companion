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
            try:
                err.close()
            except Exception:
                pass
            print(f"CLAUDE_PROVIDER_ERROR: HTTP {err.code}")
            return None
        except Exception:
            # Provider exceptions may contain request details or response text.
            # Keep logs useful for recovery without exposing prompts or secrets.
            print("CLAUDE_PROVIDER_ERROR: request failed or response was invalid")
            return None


class OpenAIProvider(BaseLLMProvider):
    """Server-side OpenAI Responses API adapter; credentials never enter the UI."""

    def __init__(self, timeout_seconds: int = 30) -> None:
        self.api_key = os.environ.get("OPENAI_API_KEY")
        self.model_name = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
        self.timeout_seconds = timeout_seconds

    def generate(self, prompt: str) -> str | None:
        if not self.api_key:
            print("OPENAI_PROVIDER_ERROR: missing OPENAI_API_KEY")
            return None
        payload = {
            "model": self.model_name,
            "instructions": (
                "You are AURA, a loyal virtual human companion. "
                "Be warm, natural, concise, emotionally present, and never robotic."
            ),
            "input": prompt,
            "max_output_tokens": 600,
        }
        try:
            data = json.dumps(payload).encode("utf-8")
            request = urllib.request.Request(
                "https://api.openai.com/v1/responses",
                data=data,
                headers={
                    "content-type": "application/json",
                    "authorization": f"Bearer {self.api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
            # Prefer the provider's convenience field, with structured output
            # traversal for API responses that omit it.
            output_text = body.get("output_text")
            if isinstance(output_text, str) and output_text.strip():
                return output_text.strip()
            for item in body.get("output", []):
                if not isinstance(item, dict):
                    continue
                for part in item.get("content", []):
                    if isinstance(part, dict) and part.get("type") == "output_text":
                        text = part.get("text")
                        if isinstance(text, str) and text.strip():
                            return text.strip()
            return None
        except urllib.error.HTTPError as err:
            try:
                err.close()
            except Exception:
                pass
            print(f"OPENAI_PROVIDER_ERROR: HTTP {err.code}")
            return None
        except Exception:
            # Provider exceptions may contain request details or response text.
            # Keep logs useful for recovery without exposing prompts or secrets.
            print("OPENAI_PROVIDER_ERROR: request failed or response was invalid")
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
        elif selected == "openai":
            self.provider = OpenAIProvider(timeout_seconds=timeout_seconds)
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
