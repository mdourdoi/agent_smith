import time
import requests


MAX_RETRIES_PER_KEY = 3
RETRY_BASE_DELAY = 2

# Transient: rotate key and retry.
TRANSIENT_STATUS = (429, 500, 502, 503, 504)
# Definitive: the request itself is wrong (bad model, bad auth). Stop.
DEFINITIVE_STATUS = (400, 401, 404)


class InvalidModelError(RuntimeError):
    """The model is unavailable/unknown/not free on this provider."""


class AllKeysExhausted(RuntimeError):
    """Every API key hit a rate limit / quota; none succeeded."""


class LLMClient:
    def __init__(
        self,
        api_keys: list[str],
        model: str,
        provider_url: str,
        stop_sequences: list[str] | None = None,
    ):
        if not api_keys:
            raise ValueError("At least one API key is required.")
        self.api_keys = api_keys
        self.model = model
        base = provider_url.rstrip("/")
        self.endpoint = (
            base if base.endswith("/chat/completions")
            else f"{base}/chat/completions"
        )
        self.stop_sequences = stop_sequences or ["<end_code>"]

    def call(self, messages: list[dict]) -> tuple[str, int, int]:
        """
        Return (text, input_tokens, output_tokens).

        Rotates through all keys on transient errors. Raises
        InvalidModelError on a definitive error, or AllKeysExhausted
        if every key fails transiently.
        """
        last_error = None

        for key in self.api_keys:
            delay = RETRY_BASE_DELAY
            for attempt in range(MAX_RETRIES_PER_KEY):
                try:
                    response = requests.post(
                        self.endpoint,
                        headers={
                            "Authorization": f"Bearer {key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.model,
                            "messages": messages,
                            "stop": self.stop_sequences,
                        },
                        timeout=60,
                    )

                    if response.status_code in DEFINITIVE_STATUS:
                        # Changing keys won't help — the request is wrong.
                        raise InvalidModelError(
                            f"Provider rejected the request "
                            f"(HTTP {response.status_code}) for model "
                            f"'{self.model}'. Check the model name exists "
                            f"and is free on this provider. "
                            f"Response: {response.text[:200]}"
                        )

                    if response.status_code in TRANSIENT_STATUS:
                        # Rate limit / server hiccup: wait, then try again,
                        # and ultimately move to the next key.
                        last_error = f"HTTP {response.status_code}"
                        time.sleep(delay)
                        delay *= 2
                        continue

                    response.raise_for_status()
                    data = response.json()

                    text = data["choices"][0]["message"]["content"]
                    usage = data.get("usage") or {}
                    return (
                        text,
                        usage.get("prompt_tokens", 0),
                        usage.get("completion_tokens", 0),
                    )

                except requests.exceptions.RequestException as e:
                    last_error = str(e)
                    time.sleep(delay)
                    delay *= 2

            # This key is exhausted; loop moves to the next one.

        raise AllKeysExhausted(
            f"All {len(self.api_keys)} API key(s) failed. "
            f"Last error: {last_error}"
        )
