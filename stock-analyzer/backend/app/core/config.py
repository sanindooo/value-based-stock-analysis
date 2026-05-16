from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/stockanalyzer"
    database_url_sync: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/stockanalyzer"
    fmp_api_key: str = ""
    anthropic_api_key: str = ""
    finnhub_api_key: str = ""
    site_secret: str = ""
    user_email: str = "admin@example.com"
    yahoo_concurrency: int = 10

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
