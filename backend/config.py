import os
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel

# Load environment variables from .env if present
load_dotenv()

class Settings(BaseModel):
    PROJECT_NAME: str = "Real-Time Multimodal Voice & Support Copilot"
    VERSION: str = "1.0.0"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # Redis configuration
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD", None)

    # Groq STT & LLM configuration
    GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY", None)
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "whisper-large-v3")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")

    # Neural TTS configuration (100% free Microsoft Edge Neural TTS)
    TTS_VOICE: str = os.getenv("TTS_VOICE", "en-US-ChristopherNeural")
    TTS_VOICE_EN: str = os.getenv("TTS_VOICE_EN", "en-US-ChristopherNeural")
    TTS_VOICE_MR: str = os.getenv("TTS_VOICE_MR", "mr-IN-AarohiNeural")
    TTS_VOICE_MR_MALE: str = os.getenv("TTS_VOICE_MR_MALE", "mr-IN-ManoharNeural")

    # Allowed CORS Origins
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "*"
    ]

    @property
    def redis_url(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

settings = Settings()
