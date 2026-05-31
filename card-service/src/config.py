from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://autopilot:autopilot@localhost:5432/cardservice"

    class Config:
        env_file = ".env"


settings = Settings()
