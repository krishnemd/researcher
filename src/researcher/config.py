"""Configuration for the research system."""

from strands.models.ollama import OllamaModel

OLLAMA_HOST = "http://localhost:11434"
MODEL_ID = "gemma4:e2b"

# Evidence limits
MAX_CONTENT_LENGTH = 4000  # Max chars to keep from a fetched page
MAX_EVIDENCE_PER_ITERATION = 5

# Time budget defaults
DEFAULT_TIME_MINUTES = 30
SHUTDOWN_THRESHOLD = 0.85  # Start final synthesis when 85% of time is used


def get_model() -> OllamaModel:
    """Create and return the shared Ollama model instance."""
    return OllamaModel(
        host=OLLAMA_HOST,
        model_id=MODEL_ID,
    )
