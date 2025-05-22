"""
logging_utils.py
----------------
Logging utilities for the Confluence Downloader CLI.
Provides logger setup and configuration helpers.
"""
import logging
from typing import Optional

def get_cli_logger(name: str, verbose: bool = False) -> logging.Logger:
    """
    Get a logger for the CLI with appropriate formatting and level.
    Args:
        name (str): Logger name.
        verbose (bool): If True, set level to DEBUG; else INFO.
    Returns:
        logging.Logger: Configured logger.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('[%(levelname)s] %(name)s: %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    return logger

def setup_cli_logging(verbose: bool = False) -> None:
    """
    Set up global logging configuration for the CLI.
    Args:
        verbose (bool): If True, set level to DEBUG; else INFO.
    """
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format='[%(levelname)s] %(name)s: %(message)s'
    ) 