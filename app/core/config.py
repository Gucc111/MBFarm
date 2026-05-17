from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    APP_NAME: str = Field(default="MB Farm", description="应用名称")
    APP_VERSION: str = Field(default="0.1.0", description="应用版本")
    DEBUG: bool = Field(default=False, description="调试模式开关")
    SECRET_KEY: str = Field(default="change-me-in-production", description="用于签名 Session 和 JWT 的密钥")
    DATABASE_URL: str = Field(default="sqlite:///./mbfarm.db", description="数据库连接字符串")
    JWT_EXPIRE_MINUTES: int = Field(default=1440, ge=1, description="JWT Token 有效期（分钟）")
    HOST: str = Field(default="0.0.0.0", description="监听地址")
    PORT: int = Field(default=8000, ge=1, le=65535, description="监听端口")


settings = Settings()
