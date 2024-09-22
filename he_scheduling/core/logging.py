import logging
import logging.config
import sys
import os
from pathlib import Path

# Define the log directory and log file path
LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "app.log"

# Create the log directory if it doesn't exist
LOG_DIR.mkdir(exist_ok=True)


def setup_logging():
    """Set up logging configuration based on the environment."""

    # Get the environment variable (default to 'development')
    env = os.getenv("ENVIRONMENT", "development")

    # Set log level based on the environment
    if env == "production":
        log_level = logging.ERROR  # Log only errors in production
    else:
        log_level = logging.DEBUG  # More verbose logging in development

    # Define log format and date format
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Logging configuration
    logging_config = {
        'version': 1,  # Schema version
        'disable_existing_loggers': False,  # Don't disable loggers from other libraries

        'formatters': {
            'default': {
                'format': log_format,
                'datefmt': date_format,
            },
            'simple': {
                'format': '%(levelname)s - %(message)s',
            },
        },

        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'stream': sys.stdout,  # Output to stdout
                'formatter': 'default',
                'level': log_level,  # Set handler level based on environment
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': LOG_FILE,
                'formatter': 'default',
                'level': log_level,  # Set file logging level
                'maxBytes': 10 * 1024 * 1024,  # 10 MB per log file
                'backupCount': 5,  # Keep up to 5 backup log files
            },
        },

        'root': {
            'handlers': ['console', 'file'],  # Attach console and file handlers
            'level': log_level,  # Set the root logger's level
        },
    }

    # Apply the logging configuration
    logging.config.dictConfig(logging_config)


# A helper function to get a logger for each module
def get_logger(name):
    """Convenience function to get a named logger."""
    return logging.getLogger(name)


# Initialize logging when this module is imported
setup_logging()
