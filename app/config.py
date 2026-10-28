"""Config: read environment variables at call time (no caching)."""
import os


def get(name, default=None):
    return os.environ.get(name, default)
