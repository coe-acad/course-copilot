import os
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

class Settings:
    """Application settings configuration"""
    
    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    OPENAI_API_VERSION: str = "assistants=v2"
    
    # Firebase Configuration
    FIREBASE_PROJECT_ID: Optional[str] = os.getenv("FIREBASE_PROJECT_ID")
    FIREBASE_PRIVATE_KEY_ID: Optional[str] = os.getenv("FIREBASE_PRIVATE_KEY_ID")
    FIREBASE_PRIVATE_KEY: Optional[str] = os.getenv("FIREBASE_PRIVATE_KEY")
    FIREBASE_CLIENT_EMAIL: Optional[str] = os.getenv("FIREBASE_CLIENT_EMAIL")
    FIREBASE_CLIENT_ID: Optional[str] = os.getenv("FIREBASE_CLIENT_ID")
    FIREBASE_AUTH_URI: str = os.getenv("FIREBASE_AUTH_URI", "https://accounts.google.com/o/oauth2/auth")
    FIREBASE_TOKEN_URI: str = os.getenv("FIREBASE_TOKEN_URI", "https://oauth2.googleapis.com/token")
    FIREBASE_AUTH_PROVIDER_X509_CERT_URL: str = os.getenv("FIREBASE_AUTH_PROVIDER_X509_CERT_URL", "https://www.googleapis.com/oauth2/v1/certs")
    FIREBASE_CLIENT_X509_CERT_URL: Optional[str] = os.getenv("FIREBASE_CLIENT_X509_CERT_URL")
    
    # Application Configuration
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # API Configuration
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    
    @classmethod
    def validate(cls) -> None:
        """Validate required settings"""
        if not cls.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required")
        
        # Firebase configuration: allow either serviceAccountKey.json or all env vars
        firebase_key_file = os.path.join(os.path.dirname(__file__), '..', 'serviceAccountKey.json')
        firebase_key_file = os.path.abspath(firebase_key_file)
        firebase_vars = [
            cls.FIREBASE_PROJECT_ID,
            cls.FIREBASE_PRIVATE_KEY_ID,
            cls.FIREBASE_PRIVATE_KEY,
            cls.FIREBASE_CLIENT_EMAIL,
            cls.FIREBASE_CLIENT_ID,
            cls.FIREBASE_CLIENT_X509_CERT_URL
        ]
        has_key_file = os.path.exists(firebase_key_file)
        has_all_env = all(firebase_vars)
        if not (has_key_file or has_all_env):
            raise ValueError("Firebase configuration missing: provide serviceAccountKey.json or set all Firebase env vars")

# Create global settings instance
settings = Settings()

# Validate settings on import
try:
    settings.validate()
except ValueError as e:
    print(f"Configuration error: {e}")
    raise 