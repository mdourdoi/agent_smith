from dataclasses import dataclass

DEFAULT_PROVIDER = "openrouter"


@dataclass(frozen=True)
class Provider:
    name: str
    url: str
    env_key: str


PROVIDERS: dict[str, Provider] = {
    "openrouter": Provider(
        "openrouter",
        "https://openrouter.ai/api/v1",
        "OPENROUTER_API_KEY",
    ),
    "groq": Provider(
        "groq",
        "https://api.groq.com/openai/v1",
        "GROQ_API_KEY",
    ),
    "mistral": Provider(
        "mistral",
        "https://api.mistral.ai/v1",
        "MISTRAL_API_KEY",
    ),
    "cerebras": Provider(
        "cerebras",
        "https://api.cerebras.ai/v1",
        "CEREBRAS_API_KEY",
    ),
}


def get_provider(name: str) -> Provider:
    """Return the Provider for a name, or raise if unknown."""
    if name not in PROVIDERS:
        known = ", ".join(sorted(PROVIDERS))
        raise ValueError(
            f"Unknown provider '{name}'. Known providers: {known}."
        )
    return PROVIDERS[name]
