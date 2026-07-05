"""Calls an OpenAI-compatible chat API. Rotates through several keys when
one hits a rate limit, and reports how many retries a call needed.
"""
import time
import requests

MAX_RETRIES_PER_KEY = 3
RETRY_BASE_DELAY = 2

# Worth retrying (rate limit / server hiccup): wait and try the next key.
TRANSIENT_STATUS = (429, 500, 502, 503, 504)
# Not worth retrying (the request itself is wrong): give up right away.
DEFINITIVE_STATUS = (400, 401, 404)


class InvalidModelError(RuntimeError):
    """The model is unknown, unavailable, or the request was rejected."""


class AllKeysExhausted(RuntimeError):
    """Every key hit a rate limit or error; none succeeded."""


class LLMClient:
    def __init__(self, api_keys: list[str], model: str, provider_url: str,
                 stop_sequences: list[str] | None = None,
                 temperature: float = 0.0, max_tokens: int | None = None):
        if not api_keys:
            raise ValueError("At least one API key is required.")
        self.api_keys = api_keys
        self.model = model
        base = provider_url.rstrip("/")
        self.endpoint = (base if base.endswith("/chat/completions")
                         else f"{base}/chat/completions")
        self.stop_sequences = stop_sequences or ["<end_code>"]
        self.temperature = temperature
        self.max_tokens = max_tokens  # cap each reply, protects the budget

    def call(self, messages: list[dict]) -> tuple[str, int, int, int]:
        """Return (text, input_tokens, output_tokens, retries).

        Raises InvalidModelError on a request that will never work, or
        AllKeysExhausted if every key failed after retrying.
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "stop": self.stop_sequences,
            "temperature": self.temperature,
        }
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens

        last_error = None
        retries = 0
        for key in self.api_keys:
            delay = RETRY_BASE_DELAY
            for _ in range(MAX_RETRIES_PER_KEY):
                try:
                    response = requests.post(
                        self.endpoint,
                        headers={"Authorization": f"Bearer {key}",
                                 "Content-Type": "application/json"},
                        json=payload,
                        timeout=60,
                    )
                    if response.status_code in DEFINITIVE_STATUS:
                        raise InvalidModelError(
                            f"Provider rejected the request "
                            f"(HTTP {response.status_code}) for model "
                            f"'{self.model}'. Check the name is right and "
                            f"free on this provider. {response.text[:200]}")
                    if response.status_code in TRANSIENT_STATUS:
                        last_error = f"HTTP {response.status_code}"
                        retries += 1
                        time.sleep(delay)
                        delay *= 2
                        continue

                    response.raise_for_status()
                    data = response.json()
                    text = data["choices"][0]["message"]["content"]
                    usage = data.get("usage") or {}
                    return (text,
                            usage.get("prompt_tokens", 0),
                            usage.get("completion_tokens", 0),
                            retries)
                except requests.exceptions.RequestException as e:
                    last_error = str(e)
                    retries += 1
                    time.sleep(delay)
                    delay *= 2

        raise AllKeysExhausted(
            f"All {len(self.api_keys)} API key(s) failed. "
            f"Last error: {last_error}")
