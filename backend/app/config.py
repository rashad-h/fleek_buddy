from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Default model per provider, used when LLM_MODEL is unset. Picked by which
# API key is configured, in this order.
PROVIDER_DEFAULTS: list[tuple[str, str]] = [
    ("openrouter_api_key", "openrouter/deepseek/deepseek-v4-flash"),
    ("anthropic_api_key", "anthropic/claude-sonnet-5"),
    ("openai_api_key", "openai/gpt-5.1"),
]
FALLBACK_DEFAULT_MODEL = "anthropic/claude-sonnet-5"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM (provider-agnostic via LiteLLM). Model format is "provider/model".
    # Set LLM_MODEL to override; otherwise the default follows your API key.
    llm_model: str = ""
    llm_fallback_model: str | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    openrouter_api_key: str | None = None

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/app"
    cors_origins: list[str] = ["*"]

    @field_validator(
        "llm_fallback_model",
        "anthropic_api_key",
        "openai_api_key",
        "openrouter_api_key",
        mode="before",
    )
    @classmethod
    def blank_to_none(cls, value: str | None) -> str | None:
        # `VAR=` lines in .env arrive as "" and would otherwise look configured.
        if value is None or not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def resolve_default_model(self) -> "Settings":
        if not self.llm_model.strip():
            self.llm_model = next(
                (model for key, model in PROVIDER_DEFAULTS if getattr(self, key)),
                FALLBACK_DEFAULT_MODEL,
            )
        return self


settings = Settings()
