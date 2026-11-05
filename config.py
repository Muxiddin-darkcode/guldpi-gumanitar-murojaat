import os
from typing import List, Optional, Any
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str = Field(default="", description="Telegram Bot Token")
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///data/e_murojaat.db",
        description="Database URL (PostgreSQL or SQLite)"
    )
    REDIS_URL: Optional[str] = Field(default=None, description="Redis URL for FSM and caching")
    SUPER_ADMIN_ID: int = Field(default=0, description="Telegram ID of Super Administrator")
    DEKAN_ID: int = Field(default=0, description="Telegram ID of Dekan")
    TIMEZONE: str = Field(default="Asia/Tashkent", description="Timezone name")
    APP_ENV: str = Field(default="production", description="Application environment: development / production")
    LOG_LEVEL: str = Field(default="INFO", description="Log level")
    MAX_FILE_SIZE_MB: int = Field(default=20, description="Max allowed file size in MB")
    APPEAL_PREFIX: str = Field(default="GF", description="Appeal number prefix (GF for Gumanitar fanlar va jismoniy madaniyat fakulteti)")
    ALLOWED_EXTENSIONS: List[str] = Field(
        default=[".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png", ".mp4", ".xlsx", ".zip", ".txt"],
        description="Allowed file extensions"
    )

    # Web server & UptimeRobot keep-alive settings
    ENABLE_WEB_SERVER: bool = Field(default=True, description="Enable HTTP server for UptimeRobot")
    WEB_HOST: str = Field(default="0.0.0.0", description="Web host to bind to")
    WEB_PORT: int = Field(default=8080, description="Web port for health checks and UptimeRobot")
    SELF_PING_URL: Optional[str] = Field(default=None, description="Optional public URL to self-ping")
    SELF_PING_INTERVAL_MINUTES: int = Field(default=10, description="Self-ping interval in minutes")

    @field_validator("SUPER_ADMIN_ID", "DEKAN_ID", mode="before")
    @classmethod
    def parse_optional_int(cls, v: Any) -> int:
        if v is None or v == "":
            return 0
        return int(v)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

