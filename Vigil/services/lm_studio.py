from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import AsyncIterator
from urllib.parse import urlparse, urlunparse

import httpx


class LMStudioClient:
    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:1234/v1",
        api_key: str | None = None,
        models_ttl_s: float = 15.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._models_ttl_s = models_ttl_s
        self._refresh_lock = asyncio.Lock()

        self.models: list[str] = []
        self.connected: bool = False
        self.last_error: str | None = None
        self._last_models_refresh_monotonic: float | None = None

    @property
    def models_url(self) -> str:
        return f"{self._base_url}/models"

    @property
    def chat_completions_url(self) -> str:
        return f"{self._base_url}/chat/completions"

    def _candidate_api_roots(self) -> list[str]:
        """Return API root candidates (hosts + common LM Studio API paths)."""
        parsed = urlparse(self._base_url)
        scheme = parsed.scheme or "http"
        hostname = parsed.hostname or "127.0.0.1"
        port = parsed.port
        path = (parsed.path or "").rstrip("/")

        # Host fallbacks: users often run into IPv4/IPv6 resolution differences on Windows.
        host_candidates = [hostname]
        loopback_hosts = {"localhost", "127.0.0.1", "::1"}
        if hostname.strip("[]") in loopback_hosts:
            host_candidates.extend(["localhost", "127.0.0.1", "[::1]"])

        # Path fallbacks: LM Studio primarily exposes OpenAI-compatible `/v1`, but some setups use `/api/v0`.
        def base_path_without(suffix: str) -> str:
            return path[: -len(suffix)] if path.endswith(suffix) else path

        base = base_path_without("/v1")
        base = base_path_without("/api/v0") if base == path else base

        path_candidates = [path, f"{base}/v1", f"{base}/api/v0", base]

        def build(host: str, api_path: str) -> str:
            clean_path = api_path if api_path else ""
            netloc = host
            if port is not None and ":" not in host.strip("[]"):
                netloc = f"{host}:{port}"
            elif port is not None and host.startswith("[") and host.endswith("]"):
                netloc = f"{host}:{port}"
            return urlunparse((scheme, netloc, clean_path, "", "", "")).rstrip("/")

        candidates: list[str] = []
        for host in host_candidates:
            for api_path in path_candidates:
                candidates.append(build(host, api_path.rstrip("/")))
        return list(dict.fromkeys(candidates))

    def _models_url_for(self, base_url: str) -> str:
        return f"{base_url.rstrip('/')}/models"

    def _chat_completions_url_for(self, base_url: str) -> str:
        return f"{base_url.rstrip('/')}/chat/completions"

    def _auth_headers(self) -> dict[str, str]:
        api_key = self._api_key or os.environ.get("LMSTUDIO_API_KEY")
        if not api_key:
            api_key = "lm-studio"
        return {"Authorization": f"Bearer {api_key}"}

    def _models_stale(self) -> bool:
        if self._last_models_refresh_monotonic is None:
            return True
        return (time.monotonic() - self._last_models_refresh_monotonic) > self._models_ttl_s

    async def refresh_models(self, *, force: bool = False) -> list[str]:
        if not force and not self._models_stale():
            return self.models

        async with self._refresh_lock:
            if not force and not self._models_stale():
                return self.models

            last_exception: Exception | None = None
            for candidate_base_url in self._candidate_api_roots():
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        url = self._models_url_for(candidate_base_url)
                        response = await client.get(url)
                        if response.status_code in (401, 403):
                            response = await client.get(url, headers=self._auth_headers())
                        response.raise_for_status()
                        data = response.json()
                        items = data.get("data", []) if isinstance(data, dict) else data
                        if not isinstance(items, list):
                            items = []
                        models: list[str] = []
                        for item in items:
                            if not isinstance(item, dict):
                                continue
                            model_id = item.get("id") or item.get("name") or item.get("model")
                            if isinstance(model_id, str) and model_id:
                                models.append(model_id)
                        self.models = models
                        self.connected = True
                        self.last_error = None if self.models else "No models returned."
                        self._last_models_refresh_monotonic = time.monotonic()
                        self._base_url = candidate_base_url.rstrip("/")
                        return self.models
                except httpx.HTTPStatusError as e:
                    last_exception = e
                    continue
                except httpx.ConnectError as e:
                    last_exception = e
                    continue
                except Exception as e:
                    last_exception = e
                    break

            self.models = []
            self.connected = False
            self.last_error = (
                "Can't connect to LM Studio. Is it running?"
                if isinstance(last_exception, httpx.ConnectError)
                else (
                    f"{last_exception.response.status_code} {last_exception.response.reason_phrase}"
                    if isinstance(last_exception, httpx.HTTPStatusError)
                    else str(last_exception)
                )
                if last_exception is not None
                else "Unknown error"
            )
            self._last_models_refresh_monotonic = time.monotonic()
            return self.models

    async def query_chat(self, *, prompt: str, context: str, model: str | None) -> str:
        messages = [
            {
                "role": "system",
                "content": "You are a concise assistant helping with git operations. Be brief and direct.",
            },
            {"role": "user", "content": f"{prompt}\n\n```\n{context}\n```"},
        ]

        payload: dict = {
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 500,
            "stream": False,
        }

        if model:
            payload["model"] = model

        last_exception: Exception | None = None
        for candidate_base_url in self._candidate_api_roots():
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    url = self._chat_completions_url_for(candidate_base_url)
                    response = await client.post(url, json=payload)
                    if response.status_code in (401, 403):
                        response = await client.post(url, json=payload, headers=self._auth_headers())
                    response.raise_for_status()
                    data = response.json()
                    self._base_url = candidate_base_url.rstrip("/")
                    return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                last_exception = e
                continue
            except httpx.ConnectError as e:
                last_exception = e
                continue
            except Exception as e:
                last_exception = e
                break

        if isinstance(last_exception, httpx.ConnectError):
            return "Error: Can't connect to LM Studio. Is it running?"
        if isinstance(last_exception, httpx.HTTPStatusError):
            return f"Error: {last_exception.response.status_code} {last_exception.response.reason_phrase}"
        return f"Error: {last_exception}" if last_exception is not None else "Error: Unknown error"

    async def query_chat_stream(
        self, *, prompt: str, context: str, model: str | None
    ) -> AsyncIterator[str]:
        """Stream chat completion tokens as they arrive."""
        messages = [
            {
                "role": "system",
                "content": "You are a concise assistant helping with git operations. Be brief and direct.",
            },
            {"role": "user", "content": f"{prompt}\n\n```\n{context}\n```"},
        ]

        payload: dict = {
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 500,
            "stream": True,
        }

        if model:
            payload["model"] = model

        last_exception: Exception | None = None
        for candidate_base_url in self._candidate_api_roots():
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    url = self._chat_completions_url_for(candidate_base_url)
                    async with client.stream(
                        "POST", url, json=payload, headers=self._auth_headers()
                    ) as response:
                        if response.status_code in (401, 403):
                            continue
                        response.raise_for_status()
                        self._base_url = candidate_base_url.rstrip("/")

                        async for line in response.aiter_lines():
                            if not line.startswith("data: "):
                                continue
                            data_str = line[6:]  # Strip "data: " prefix
                            if data_str.strip() == "[DONE]":
                                return
                            try:
                                data = json.loads(data_str)
                                delta = data.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                continue
                        return
            except httpx.HTTPStatusError as e:
                last_exception = e
                continue
            except httpx.ConnectError as e:
                last_exception = e
                continue
            except Exception as e:
                last_exception = e
                break

        if isinstance(last_exception, httpx.ConnectError):
            yield "Error: Can't connect to LM Studio. Is it running?"
        elif isinstance(last_exception, httpx.HTTPStatusError):
            yield f"Error: {last_exception.response.status_code} {last_exception.response.reason_phrase}"
        else:
            yield f"Error: {last_exception}" if last_exception is not None else "Error: Unknown error"
