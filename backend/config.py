import os
from typing import Optional, List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    PROJECT_NAME: str = "VoiceDesk AI"
    VERSION: str = "1.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # PostgreSQL Database URL
    DATABASE_URL: str = "postgresql+asyncpg://voicedesk:voicedesk_dev_password@localhost:5432/voicedesk"

    # Redis configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    # Groq STT & LLM configuration
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "whisper-large-v3"
    LLM_MODEL: str = "openai/gpt-oss-120b"

    # Neural TTS configuration (Microsoft Edge Neural TTS)
    TTS_VOICE: str = "en-US-ChristopherNeural"
    TTS_VOICE_EN: str = "en-US-ChristopherNeural"
    TTS_VOICE_MR: str = "mr-IN-AarohiNeural"
    TTS_VOICE_MR_MALE: str = "mr-IN-ManoharNeural"

    # Allowed CORS Origins
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "*"
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["*"]

    @property
    def redis_url(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


settings = Settings()
