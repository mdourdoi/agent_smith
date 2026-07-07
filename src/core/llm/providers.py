"""Known LLM providers and how to pick a model, provider URL and API key."""
from dataclasses import dataclass
from urllib.parse import urlparse

DEFAULT_PROVIDER = "cerebras"

DEFAULT_MODEL = "gemma-4-31b"


@dataclass(frozen=True)
class Provider:
    name: str
    url: str
    env_key: str


PROVIDERS: dict[str, Provider] = {
    "openrouter": Provider("openrouter",
                           "https://openrouter.ai/api/v1",
                           "OPENROUTER_API_KEY"),
    "groq": Provider("groq",
                     "https://api.groq.com/openai/v1",
                     "GROQ_API_KEY"),
    "mistral": Provider("mistral",
                        "https://api.mistral.ai/v1",
                        "MISTRAL_API_KEY"),
    "cerebras": Provider("cerebras",
                         "https://api.cerebras.ai/v1",
                         "CEREBRAS_API_KEY"),
    "together": Provider("together",
                         "https://api.together.xyz/v1",
                         "TOGETHER_API_KEY"),
}


def get_provider(name: str) -> Provider:
    if name not in PROVIDERS:
        known = ", ".join(sorted(PROVIDERS))
        raise ValueError(f"Unknown provider '{name}'. Known: {known}.")
    return PROVIDERS[name]


def resolve(provider_name: str, provider_url: str | None) -> Provider:
    """Resolve to one of the hardcoded providers, by name or by URL. We only
    handle the providers in PROVIDERS; anything else raises a clear error."""
    if provider_url:
        host = urlparse(provider_url).netloc.lower()
        for known in PROVIDERS.values():
            if urlparse(known.url).netloc.lower() == host:
                return Provider(known.name, provider_url, known.env_key)
        raise ValueError(
            f"Provider URL '{provider_url}' is not one we handle. "
            f"Known providers: {', '.join(sorted(PROVIDERS))}. "
            f"Use --provider, or add it to PROVIDERS in providers.py.")
    return get_provider(provider_name)


def resolve_model(cli_model: str | None) -> str:
    """The --model-name value, or the built-in default."""
    return cli_model or DEFAULT_MODEL


def candidate_env_keys(provider: Provider) -> list[str]:
    """Env-var names to try for API keys, most specific first."""
    names: list[str] = []
    if provider.env_key:
        names.append(provider.env_key)
    for known in PROVIDERS.values():
        if known.env_key not in names:
            names.append(known.env_key)
    for generic in ("LLM_API_KEY", "API_KEY"):
        if generic not in names:
            names.append(generic)
    return names
