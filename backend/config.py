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

# Database Configuration
# Check if running in Lambda with individual DB variables
DB_HOST = os.getenv("DB_HOST", "")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")  # Can come from env
DB_SECRET_ARN = os.getenv("DB_SECRET_ARN", "")

# Lazy loader for DB password from Secrets Manager
_db_password_cache = None

def get_db_password():
    """Get database password (from env or Secrets Manager)."""
    global _db_password_cache
    
    # Return cached value if available
    if _db_password_cache is not None:
        return _db_password_cache
    
    # Try environment variable first
    if DB_PASSWORD:
        _db_password_cache = DB_PASSWORD
        return _db_password_cache
    
    # Try Secrets Manager
    if DB_SECRET_ARN:
        try:
            import boto3
            import json
            secrets_client = boto3.client('secretsmanager', region_name='us-west-1')
            secret = secrets_client.get_secret_value(SecretId=DB_SECRET_ARN)
            secret_dict = json.loads(secret['SecretString'])
            _db_password_cache = secret_dict.get('password', '')
            return _db_password_cache
        except Exception as e:
            print(f"Warning: Could not get DB password from Secrets Manager: {e}")
    
    return ""

def get_database_url():
    """Build DATABASE_URL lazily (not at import time)."""
    if DB_HOST and DB_USER:
        password = get_db_password()
        if password:
            return f"postgresql://{DB_USER}:{password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return os.getenv("DATABASE_URL", "")

# For backwards compatibility - but this is now lazy
DATABASE_URL = ""  # Will be built on first use
USE_POSTGRES = bool(DB_HOST and DB_USER)  # True if DB vars are set

def get_db_path(user_id: str = DEFAULT_USER_ID) -> Path:
    """Get SQLite database path for a user (used when DATABASE_URL not set)."""
    user_dir = WORKSPACE_DIR / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / "gym.db"

# LLM Configuration
USE_OPENAI = os.getenv("USE_OPENAI", "false").lower() == "true"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Model settings
LLM_MODEL = "gpt-4o-mini" if USE_OPENAI else "claude-haiku-4-5"
LLM_MAX_TOKENS = 200

# Auth0 Configuration
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "")
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID", "")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE", "")
AUTH0_ALGORITHMS = ["RS256"]
