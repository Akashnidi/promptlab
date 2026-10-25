import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import groq


class AIProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> Dict[str, Any]:
        """Generate a response from the AI provider.

        Returns:
            {
                "content": str,
                "model": str,
                "provider": str,
                "usage": {
                    "prompt_tokens": int,
                    "completion_tokens": int,
                    "total_tokens": int
                },
                "latency_ms": float
            }
        """
        pass


class GroqProvider(AIProvider):
    MODELS = [
        "allam-2-7b",
        "qwen/qwen3.8-27b",
        "openai/gpt-oss-20b",
        "openai/gpt-oss-120b",
    ]

    DEFAULT_FALLBACK_MODELS = [
        "allam-2-7b",
        "qwen/qwen3.8-27b",
        "openai/gpt-oss-20b",
        "openai/gpt-oss-120b",
    ]

    # In-memory cache for live models list (10-minute TTL)
    _CACHE: Dict[str, Any] = {
        "models": [],
        "timestamp": 0.0,
    }
    CACHE_TTL_SECONDS = 600  # 10 minutes

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = groq.AsyncGroq(api_key=api_key)

    async def list_available_models(self) -> List[str]:
        """Fetch live chat models from Groq API, filtered and cached for 10 minutes."""
        now = time.time()
        # Return cached list if still fresh
        if self._CACHE["models"] and (now - self._CACHE["timestamp"] < self.CACHE_TTL_SECONDS):
            return list(self._CACHE["models"])

        if not self.api_key:
            return list(self.DEFAULT_FALLBACK_MODELS)

        try:
            response = await self.client.models.list()
            chat_models = []

            for item in response.data:
                m_id = getattr(item, "id", None) or (item.get("id") if isinstance(item, dict) else str(item))
                if not m_id:
                    continue

                is_active = getattr(item, "active", True)
                if isinstance(item, dict) and "active" in item:
                    is_active = item["active"]
                if not is_active:
                    continue

                # Exclude audio/whisper/guard and third-party terms models (canopylabs/orpheus)
                m_id_lower = m_id.lower()
                if any(x in m_id_lower for x in ["whisper", "tts", "guard", "canopylabs", "orpheus"]):
                    continue

                chat_models.append(m_id)

            # Sort model IDs
            unique_models = sorted(list(set(chat_models)))
            if not unique_models:
                unique_models = list(self.DEFAULT_FALLBACK_MODELS)

            # Update cache
            self._CACHE["models"] = unique_models
            self._CACHE["timestamp"] = now
            return list(unique_models)
        except Exception:
            # Fallback to cache if available, or sensible defaults
            if self._CACHE["models"]:
                return list(self._CACHE["models"])
            return list(self.DEFAULT_FALLBACK_MODELS)

    async def generate(
        self,
        prompt: str,
        model: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> Dict[str, Any]:
        messages: List[Dict[str, str]] = []
        if system_prompt and system_prompt.strip():
            messages.append({"role": "system", "content": system_prompt.strip()})
        messages.append({"role": "user", "content": prompt})

        start_time = time.perf_counter()
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except groq.APIStatusError as e:
            raise Exception(f"Groq API Error ({e.status_code}): {e.message}") from e
        except groq.APIConnectionError as e:
            raise Exception(f"Failed to connect to Groq API: {str(e)}") from e
        except groq.APIError as e:
            raise Exception(f"Groq Error: {str(e)}") from e
        except Exception as e:
            raise Exception(f"Unexpected error communicating with Groq: {str(e)}") from e

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        content = ""
        if response.choices and len(response.choices) > 0:
            content = response.choices[0].message.content or ""

        usage = {
            "prompt_tokens": getattr(response.usage, "prompt_tokens", 0) if response.usage else 0,
            "completion_tokens": getattr(response.usage, "completion_tokens", 0) if response.usage else 0,
            "total_tokens": getattr(response.usage, "total_tokens", 0) if response.usage else 0,
        }

        return {
            "content": content,
            "model": model,
            "provider": "groq",
            "usage": usage,
            "latency_ms": latency_ms,
        }


PROVIDER_MODELS: Dict[str, List[str]] = {
    "groq": GroqProvider.MODELS,
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
    "anthropic": ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022"],
    "google": ["gemini-2.0-flash", "gemini-2.5-flash"],
}


def get_provider(provider_name: str, api_key: str) -> AIProvider:
    name = provider_name.strip().lower()
    if name == "groq":
        return GroqProvider(api_key=api_key)
    raise ValueError(f"Unknown provider: {provider_name}")
