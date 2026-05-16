from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/stockanalyzer"
    database_url_sync: str = ""
    fmp_api_key: str = ""
    anthropic_api_key: str = ""
    finnhub_api_key: str = ""
    site_secret: str = ""
    user_email: str = "admin@example.com"
    yahoo_concurrency: int = 10

    model_config = {"env_file": ".env", "extra": "ignore"}

    @model_validator(mode="after")
    def _fix_db_drivers(self) -> "Settings":
        # Railway provides postgresql:// — ensure correct driver prefixes
        base = self.database_url.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg2://", "postgresql://")
        if not base.startswith("postgresql://"):
            base = self.database_url
        self.database_url = base.replace("postgresql://", "postgresql+asyncpg://", 1)
        if not self.database_url_sync:
            self.database_url_sync = base.replace("postgresql://", "postgresql+psycopg2://", 1)
        return self


settings = Settings()
