from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM (provider-agnostic via LiteLLM). Model format is "provider/model".
    # Swap providers by editing these lines only; keys are read from the env.
    llm_model: str = "anthropic/claude-sonnet-5"
    llm_fallback_model: str | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/app"
    cors_origins: list[str] = ["*"]


settings = Settings()
