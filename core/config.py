"""
Global AI-OS Configuration
"""

import os
from dotenv import load_dotenv

# -----------------------
# Load Environment Variables
# -----------------------

load_dotenv()

# ==========================================================
# AI SETTINGS
# ==========================================================

DEFAULT_PROVIDER = "ollama"
DEFAULT_MODEL = "llama3"

# ==========================================================
# API KEYS
# ==========================================================

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# ==========================================================
# PROJECT PATHS
# ==========================================================

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_FOLDER = os.path.join(PROJECT_ROOT, "data")
LOG_FOLDER = os.path.join(PROJECT_ROOT, "logs")
MEMORY_FOLDER = os.path.join(PROJECT_ROOT, "memory")
PROMPTS_FOLDER = os.path.join(PROJECT_ROOT, "prompts")
WORKFLOW_FOLDER = os.path.join(PROJECT_ROOT, "workflow")

# Create folders automatically if they don't exist
for folder in (
    DATA_FOLDER,
    LOG_FOLDER,
    MEMORY_FOLDER,
    PROMPTS_FOLDER,
    WORKFLOW_FOLDER,
):
    os.makedirs(folder, exist_ok=True)