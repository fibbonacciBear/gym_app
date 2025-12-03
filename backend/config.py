"""Application configuration."""
import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent.parent
WORKSPACE_DIR = BASE_DIR / "workspace"
DEFAULT_USER_ID = "default"

# Database
def get_db_path(user_id: str = DEFAULT_USER_ID) -> Path:
    """Get database path for a user."""
    user_dir = WORKSPACE_DIR / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / "gym.db"

# LLM (for later sprints)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = "gpt-4o-mini"
LLM_MAX_TOKENS = 200
