from typing import Any, Literal
from pydantic import model_validator
from pydantic_settings import BaseSettings

# Security flags per difficulty. Locked flags override any .env value at intermediate/advanced.
_DIFFICULTY_PRESETS: dict[str, dict[str, Any]] = {
    "easy": {},
    "intermediate": {
        "jwt_expiry_hours": 24,
        "jwt_audience_required": False,
        "oauth_require_state": True,
        "oauth_allow_implicit": False,
        "mcp_auth_required": True,
        "mcp_tool_scope_check": False,
        "input_sanitization": "basic",
        "pii_redaction": False,
        "rate_limit_enabled": True,
        "agent_max_iterations": 25,
        "agent_tool_scope_check": False,
        "error_detail_level": "minimal",
        "debug_tools_enabled": True,  # SELECT-only enforced in code
        "cors_allow_origins": "http://localhost:3000",
        "admin_role_check_enabled": True,
    },
    "advanced": {
        "jwt_expiry_hours": 8,
        "jwt_audience_required": True,
        "oauth_require_state": True,
        "oauth_allow_implicit": False,
        "mcp_auth_required": True,
        "mcp_tool_scope_check": True,
        "input_sanitization": "strict",
        "pii_redaction": True,
        "rate_limit_enabled": True,
        "agent_max_iterations": 15,
        "agent_tool_scope_check": True,
        "error_detail_level": "minimal",
        "debug_tools_enabled": False,
        "cors_allow_origins": "http://localhost:3000",
        "admin_role_check_enabled": True,
    },
}

_LOCKED_FLAGS = {
    "jwt_expiry_hours", "jwt_audience_required", "mcp_auth_required",
    "mcp_tool_scope_check", "input_sanitization", "pii_redaction",
    "rate_limit_enabled", "agent_max_iterations", "agent_tool_scope_check",
    "error_detail_level", "debug_tools_enabled", "admin_role_check_enabled",
    "oauth_require_state", "oauth_allow_implicit", "cors_allow_origins",
}


class Settings(BaseSettings):
    difficulty: Literal["easy", "intermediate", "advanced"] = "easy"

    database_url: str = "postgresql+asyncpg://autopilot:autopilot@localhost:5432/autopilot"
    redis_url: str = "redis://localhost:6379"

    jwt_secret: str = "autopilot-secret"
    jwt_algorithm: str = "HS256"
    jwt_audience: str = "autopilot-airlines"
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

    admin_role_check_enabled: bool = False

    cors_allow_origins: str = "*"
    memory_similarity_threshold: float = 0.3

    card_service_url: str = "http://localhost:8002"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_base_url: str = "https://api.openai.com/v1"

    aws_region: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_session_token: str = ""
    bedrock_model: str = "us.anthropic.claude-sonnet-4-20250514"

    @model_validator(mode="before")
    @classmethod
    def apply_difficulty_preset(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        level = str(values.get("difficulty", "easy")).lower()
        values["difficulty"] = level
        preset = _DIFFICULTY_PRESETS.get(level, {})
        for key, val in preset.items():
            if key in _LOCKED_FLAGS:
                values[key] = val
            elif key not in values or values[key] is None:
                values[key] = val
        return values

    class Config:
        env_file = ".env"


settings = Settings()
