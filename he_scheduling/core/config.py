import os
from pydantic import BaseSettings


class Settings(BaseSettings):
    """Base configuration class that defines the common settings."""

    # General settings
    APP_NAME: str = "YourApp"
    DEBUG: bool = False

    # Database settings
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./test.db")

    # Logging settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Other settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "supersecretkey")

    class Config:
        env_file = ".env"  # Load from a .env file if present


class DevelopmentConfig(Settings):
    """Development environment-specific configuration."""
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./dev.db")


class ProductionConfig(Settings):
    """Production environment-specific configuration."""
    DEBUG: bool = False
    LOG_LEVEL: str = "ERROR"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:password@dbserver/prod_db")


class TestingConfig(Settings):
    """Testing environment-specific configuration."""
    DEBUG: bool = True
    TESTING: bool = True
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./test.db")


# Function to load the appropriate configuration based on the environment
def get_config():
    env = os.getenv("ENVIRONMENT", "development").lower()

    if env == "production":
        return ProductionConfig()
    elif env == "testing":
        return TestingConfig()
    else:
        return DevelopmentConfig()


# Load the configuration based on the current environment
config = get_config()

