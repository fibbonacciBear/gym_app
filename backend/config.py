"""Application configuration."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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

# LLM Configuration
USE_OPENAI = os.getenv("USE_OPENAI", "false").lower() == "true"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Model settings
LLM_MODEL = "gpt-4o-mini" if USE_OPENAI else "claude-3-5-haiku-20241022"
LLM_MAX_TOKENS = 200
