"""
AI-OS Logger
"""

import logging
import os
from datetime import datetime

from core.config import LOG_FOLDER

# Create log folder if it doesn't exist
os.makedirs(LOG_FOLDER, exist_ok=True)

# Log file name (one file per day)
log_file = os.path.join(
    LOG_FOLDER,
    f"{datetime.now().strftime('%Y-%m-%d')}.log"
)

logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

def log(message):
    logging.info(message)

    if __debug__:
        print(f"[LOG] {message}")