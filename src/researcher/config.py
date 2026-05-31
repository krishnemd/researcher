"""Configuration for the research system."""

import time
import logging
from typing import Optional

from strands.models.ollama import OllamaModel

logger = logging.getLogger(__name__)

OLLAMA_HOST = "http://localhost:11434"
MODEL_ID = "gemma4:e2b"

# Evidence limits
MAX_CONTENT_LENGTH = 4000  # Max chars to keep from a fetched page
MAX_EVIDENCE_PER_ITERATION = 5

# Time budget defaults
DEFAULT_TIME_MINUTES = 30
SHUTDOWN_THRESHOLD = 0.85  # Start final synthesis when 85% of time is used

# Retry settings
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # seconds, doubles each retry


def get_model() -> OllamaModel:
    """Create and return the shared Ollama model instance."""
    return OllamaModel(
        host=OLLAMA_HOST,
        model_id=MODEL_ID,
    )


def get_json_model() -> OllamaModel:
    """Create a model configured for JSON output."""
    return OllamaModel(
        host=OLLAMA_HOST,
        model_id=MODEL_ID,
        model_config={"format": "json"},
    )


def call_with_retry(fn, *args, max_retries: int = MAX_RETRIES, **kwargs) -> Optional[str]:
    """Call a function with exponential backoff retry on failure.

    Returns the result string or None if all retries fail.
    """
    for attempt in range(max_retries):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"All {max_retries} retries failed: {e}")
                return None
            delay = RETRY_BASE_DELAY * (2 ** attempt)
            logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f}s...")
            time.sleep(delay)
