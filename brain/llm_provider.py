from __future__ import annotations

import http.client
import ipaddress
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from typing import Any

from config.env_loader import load_env_file


class BaseLLMProvider:
    def generate(self, prompt: str) -> str | None:
        raise NotImplementedError


class OllamaProvider(BaseLLMProvider):
    """Send prompts only to an explicitly local Ollama HTTP endpoint."""
    MAX_PROMPT_CHARS = 20000
    MAX_RESPONSE_BYTES = 1024 * 1024
    MAX_REPLY_CHARS = 16000

    def __init__(
        self,
        model_name: str = "llama3.1",
        ollama_url: str = "http://127.0.0.1:11434/api/generate",
        timeout_seconds: int = 20,
    ) -> None:
        self.model_name = model_name
        self.ollama_url = ollama_url
        self.timeout_seconds = timeout_seconds

    def _endpoint(self) -> tuple[str, int, str] | None:
        try:
            parsed = urlsplit(self.ollama_url)
            address = ipaddress.ip_address(parsed.hostname or "")
            if (parsed.scheme != "http" or not address.is_loopback
                    or parsed.username or parsed.password or parsed.query
                    or parsed.fragment or parsed.path != "/api/generate"):
                return None
            port = parsed.port or 80
            if not 1 <= port <= 65535:
                return None
            host = address.compressed
            path = "/api/generate"
            return host, port, path
        except (ValueError, TypeError):
            return None

    def generate(self, prompt: str) -> str | None:
        endpoint = self._endpoint()
        if (endpoint is None or not isinstance(prompt, str) or not prompt.strip()
                or len(prompt) > self.MAX_PROMPT_CHARS
                or not isinstance(self.model_name, str) or not self.model_name.strip()
                or len(self.model_name) > 128):
            return None

        connection = http.client.HTTPConnection(
            endpoint[0], endpoint[1], timeout=self.timeout_seconds
        )
        try:
            payload = json.dumps({
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
            }).encode("utf-8")
            connection.request(
                "POST", endpoint[2], body=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
            response = connection.getresponse()
            if response.status != 200:
                return None
            body = response.read(self.MAX_RESPONSE_BYTES + 1)
            if len(body) > self.MAX_RESPONSE_BYTES:
                return None
            parsed = json.loads(body.decode("utf-8"))
            text = parsed.get("response") if isinstance(parsed, dict) else None
            if isinstance(text, str) and text.strip() and len(text) <= self.MAX_REPLY_CHARS:
                return text.strip()
            return None
        except (http.client.HTTPException, TimeoutError, OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
            return None
        finally:
            connection.close()


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
            self.provider = OllamaProvider(
                model_name=os.environ.get("OLLAMA_MODEL", "llama3.1"),
                ollama_url=os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/generate"),
                timeout_seconds=timeout_seconds,
            )
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
