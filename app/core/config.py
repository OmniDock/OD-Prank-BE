from pydantic import Field, ConfigDict
from pydantic_settings import BaseSettings
from typing import List
from dotenv import load_dotenv

load_dotenv('.env.local')

class Settings(BaseSettings):
    # Environment
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=True)
    
    # FastAPI
    SECRET_KEY: str = Field(default="your-secret-key-change-in-production")
    API_V1_STR: str = Field(default="/api/v1")
    
    # Supabase
    SUPABASE_URL: str = Field(default="https://your-project.supabase.co")
    SUPABASE_ANON_KEY: str = Field(default="")
    SUPABASE_SERVICE_ROLE_KEY: str = Field(default="")
    SUPABASE_JWT_SECRET: str = Field(default="your-super-secret-jwt-token-with-at-least-32-characters-long")
    
    STORAGE_BUCKET_VOICE_LINES: str = Field(default="voice-lines")
    
    # Database
    DATABASE_URL: str = Field(default="postgresql://postgres:password@localhost:5432/your_db")
    
    # LangChain & AI
    OPENAI_API_KEY: str = Field(default="")
    ANTHROPIC_API_KEY: str = Field(default="")
 
    LANGCHAIN_API_KEY: str = Field(default="")
    LANGCHAIN_TRACING_V2: bool = Field(default=False)
    LANGCHAIN_ENDPOINT: str = Field(default="https://api.smith.langchain.com")
    LANGCHAIN_PROJECT: str = Field(default="your-project-name")
    
    # Logging
    LOG_DIR: str = Field(default="logs")
    LOG_LEVEL: str = Field(default="INFO")
    LOG_FORMAT: str = Field(default="console")
    LOG_FILE_ENABLED: bool = Field(default=False)
    LOG_FILE_MAX_SIZE: int = Field(default=10485760)
    LOG_FILE_BACKUP_COUNT: int = Field(default=5)
    
    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379")
    
    # ElevenLabs
    ELEVENLABS_API_KEY: str = Field(default="")
    ELEVENLABS_AGENT_ID: str = Field(default="agent_6101k2hvvyege6k91757ph92vc64")
    
    # Telnyx Voice API
    TELNYX_API_KEY: str = Field(default="")
    TELNYX_PHONE_NUMBER: str = Field(default="")
    TELNYX_APPLICATION_ID: str = Field(default="")
    TELNYX_WEBHOOK_SECRET: str = Field(default="")
    TELNYX_WEBHOOK_BASE_URL: str = Field(default="")
    TUNNEL_URL: str = Field(default="")
    
    # Telnyx WebRTC (On-Demand Credentials)
    TELNYX_CONNECTION_ID: str = Field(default="")  # OD-Backend Credential Connection
    TELNYX_SIP_USERNAME: str = Field(default="")  # SIP username for WebRTC (optional)
    TELNYX_SIP_PASSWORD: str = Field(default="")  # SIP password for WebRTC (optional)


    # CORS
    BACKEND_CORS_ORIGINS: str = Field(default="http://localhost:3000,http://localhost:8080")

    
    @property
    def cors_origins(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",")]


    model_config = ConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        case_sensitive=True
    )


settings = Settings()