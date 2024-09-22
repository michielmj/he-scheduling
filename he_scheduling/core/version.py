# Get the version from pyproject.toml dynamically
import importlib


def get_version():
    try:
        return importlib.metadata.version("he_scheduling")
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0"  # Fallback version for local development
