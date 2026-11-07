"""
AtomicDB Portable - Logging Subsystem
Configures rotating logs confined strictly to the USB storage directory.
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional

def setup_portable_logging(base_dir: str, log_level: int = logging.INFO) -> logging.Logger:
    """Configures root logger with console and USB-confined rotating file handler."""
    log_dir = os.path.join(base_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "atomicdb_client.log")

    logger = logging.getLogger("AtomicDB")
    logger.setLevel(log_level)

    # Avoid duplicate handlers on re-init
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Rotating file handler (max 5MB x 3 backups = 15MB max on USB)
    try:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Could not initialize file logger on USB (media may be read-only): {e}")

    return logger
