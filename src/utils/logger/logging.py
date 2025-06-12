"""
Simplified logging utilities.
"""

from src.utils.logger.logging_manager import (
    get_logger as get_general_logger,
    log_data,
)

# Export the inspection logger
logger = get_general_logger()

__all__ = ["logger", "log_data"]
