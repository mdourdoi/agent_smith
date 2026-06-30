import time
import requests

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

MAX_RETRIES = 5
RETRY_BASE_DELAY = 2


class LLMClient:
    def __init__(self, api_keys: list[str], model: str, stop_sequences: list[str] | None = None):
        if not api_keys:
            raise ValueError("At least one API key is required.")
        self.api_keys = api_keys
        self.model = model
        self.stop_sequences = stop_sequences or ["```\n", "<end_code>"]
        self._key_index = 0

    def _current_key(self) -> str:
        return self.api_keys[self._key_index]

    def _rotate_key(self) -> None:
        self._key_index = (self._key_index + 1) % len(self.api_keys)

    def call(self, messages: list[dict]) -> tuple[str, int, int]:
        delay = RETRY_BASE_DELAY

        for attempt in range(MAX_RETRIES):
            try:
                response = requests.post(
                    OPENROUTER_API_URL,
                    headers={
                        "Authorization": f"Bearer {self._current_key()}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stop": self.stop_sequences,
                    },
                    timeout=60,
                )

                if response.status_code in (429, 500, 502, 503, 504):
                    self._rotate_key()
                    time.sleep(delay)
                    delay *= 2
                    continue

                response.raise_for_status()
                data = response.json()

                text = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)

                return text, input_tokens, output_tokens

            except requests.exceptions.RequestException as e:
                if attempt == MAX_RETRIES - 1:
                    raise RuntimeError(f"LLM API call failed after {MAX_RETRIES} attempts: {e}")
                time.sleep(delay)
                delay *= 2

        raise RuntimeError(f"LLM API call failed after {MAX_RETRIES} attempts.")