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

    model_config = SettingsConfigDict(env_file='.env', extra='allow')

    # General settings
    app_name: str = "he_scheduling"
    debug: bool = False

    # Celery settings
    celery_broker: Union[AmqpDsn, RedisDsn] = Field('amqp://guest@localhost/', alias="CELERY_BROKER")
    celery_result_backend: SQLAlchemyDSN = Field('db+postgresql://root@localhost/postgres',
                                                 alias="CELERY_RESULT_BACKEND")

    # Logging settings
    log_level: str = Field("INFO", alias="LOG_LEVEL")


class ProductionConfig(Settings):
    pass


class DevelopmentConfig(Settings):
    pass


class TestingConfig(Settings):
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
