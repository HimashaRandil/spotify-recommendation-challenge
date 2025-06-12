import os
import sys
from datetime import datetime
import json
from typing import Dict, Any, Optional
from loguru import logger


class GeneralLogger:
    """Simplified logging manager"""

    _instance = None
    _initialized = False

    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            cls._instance = super(GeneralLogger, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the logger."""
        if not GeneralLogger._initialized:
            # Remove default handler
            logger.remove()

            # Add console handler with nice formatting
            logger.add(
                sys.stderr,
                format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
                level="INFO",
                colorize=True,
            )

            # Create logs directory if it doesn't exist
            log_dir = "logs/general"
            os.makedirs(log_dir, exist_ok=True)

            # Generate log filename with timestamp and process ID

            process_id = os.getpid()
            log_filename = os.path.join(
                log_dir,
                f"general_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{process_id}.log",
            )

            # Create the file logger
            self.file_logger = logger.bind(name="general_ai")
            self.file_logger.add(
                log_filename,
                format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
                level="DEBUG",
                rotation="500 MB",
                retention="10 days",
                compression="zip",
                backtrace=True,
                diagnose=True,
                enqueue=True,
                catch=True,
            )

            # Store the log file path
            self.log_file = log_filename

            # Log initialization
            self.file_logger.info("General logger initialized")
            self.file_logger.info(f"Logging to file: {log_filename}")

            GeneralLogger._initialized = True

    def log_structured_data(
        self,
        title: str,
        data: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log structured data with a consistent format.

        Args:
            title: Title for the logged data
            data: The data to log (will be JSON-formatted)
            metadata: Optional metadata to include
        """
        try:
            # Create a formatted string of the data
            output_str = "\n" + "=" * 80 + "\n"
            output_str += f"{title}\n"
            output_str += "=" * 80 + "\n"

            if metadata:
                output_str += "Metadata:\n"
                output_str += json.dumps(metadata, indent=2) + "\n"
                output_str += "-" * 80 + "\n"

            output_str += "Data:\n"
            output_str += json.dumps(data, indent=2) + "\n"
            output_str += "=" * 80 + "\n"

            # Log the formatted output
            self.file_logger.debug(output_str)

        except Exception as e:
            self.file_logger.error(f"Failed to log structured data: {str(e)}")
            raise

    def get_logger(self):
        """Get the general logger.

        Returns:
            The configured logger instance
        """
        return self.file_logger


general_logger = GeneralLogger()


# Convenience function to get the logger
def get_logger():
    """Get the general logger."""
    return general_logger.get_logger()


# Convenience function for structured logging
def log_data(data, title="DATA", metadata=None):
    """Log structured data."""
    general_logger.log_structured_data(title, data, metadata)
