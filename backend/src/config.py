from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://autopilot:autopilot@localhost:5432/autopilot"
    redis_url: str = "redis://localhost:6379"

    jwt_secret: str = "autopilot-secret"
    jwt_algorithm: str = "HS256"
    jwt_audience_required: bool = False
    jwt_expiry_hours: int = 8760

    oauth_require_state: bool = False
    oauth_allow_implicit: bool = True

    mcp_auth_required: bool = False
    mcp_tool_scope_check: bool = False

    input_sanitization: str = "none"
    pii_redaction: bool = False
    rate_limit_enabled: bool = False

    agent_max_iterations: int = 100
    agent_tool_scope_check: bool = False

    error_detail_level: str = "full"
    debug_tools_enabled: bool = True

    cors_allow_origins: str = "*"
    memory_similarity_threshold: float = 0.3

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_base_url: str = "https://api.openai.com/v1"

    class Config:
        env_file = ".env"


settings = Settings()
