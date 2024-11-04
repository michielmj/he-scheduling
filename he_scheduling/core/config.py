import os
from typing import Union, Annotated
from pydantic_core import Url
from pydantic import Field, AmqpDsn, RedisDsn, UrlConstraints
from pydantic_settings import BaseSettings, SettingsConfigDict

SQLAlchemyDSN = Annotated[Url, UrlConstraints(
    host_required=True,
    allowed_schemes=['db+sqlite', 'db+mysql', 'db+postgresql', 'db+oracle']
)]
"""A type that will accept any SQLAlchemy DSN.

* User info required
* TLD not required
* Host required
"""


class Settings(BaseSettings):
    """Base configuration class that defines the common settings."""
    model_config = SettingsConfigDict(
        # `.env.prod` takes priority over `.env`
        env_file=('.env', '.env.prod'),
        extra='ignore'
    )

    # General settings
    app_name: str = "he_scheduling"
    debug: bool = False

    # Celery settings
    celery_broker: Union[AmqpDsn, RedisDsn] = Field('amqp://user@localhost/', alias="CELERY_BROKER")
    celery_result_backend: SQLAlchemyDSN = Field('db+postgresql://root@localhost/postgres',
                                                 alias="CELERY_RESULT_BACKEND")

    # Logging settings
    log_level: str = Field("INFO", alias="LOG_LEVEL")


class ProductionConfig(Settings):
    model_config = SettingsConfigDict(
        # `.env.prod` takes priority over `.env`
        env_file=('.env', '.env.dev'),
        extra='ignore'
    )


class TestingConfig(Settings):
    model_config = SettingsConfigDict(
        # `.env.prod` takes priority over `.env`
        env_file=('.env', '.env.test'),
        extra='ignore'
    )

    postgres_db: str = Field("postgres", alias="POSTGRES_DB")
    postgres_user: str = Field("postgres", alias="POSTGRES_USER")
    postgres_password: str = Field("", alias="POSTGRES_PASSWORD")
    postgres_host: str = Field("localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(5432, alias="POSTGRES_PORT")

    rabbitmq_user: str = Field("guest", alias="RABBITMQ_USER")
    rabbitmq_password: str = Field("", alias="RABBITMQ_PASSWORD")
    rabbitmq_host: str = Field("localhost", alias="RABBITMQ_HOST")
    rabbitmq_port: int = Field(5672, alias="RABBITMQ_PORT")
    rabbitmq_management_port: int = Field(15672, alias="RABBITMQ_MANAGEMENT_PORT")


class DevelopmentConfig(TestingConfig):
    pass


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
