"""
Configuration file for Telegram Weather Bot.

This module loads configuration from environment variables.
Make sure to set the required variables in your .env file or environment.
"""

import os
from typing import Optional


def _load_env_file(path: str = ".env") -> None:
    """
    Load environment variables from .env file.
    Supports KEY=VALUE format, empty lines, and # comments.
    """
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        # If .env is corrupted/in wrong encoding, just ignore it
        return


# Load .env file if it exists
_load_env_file()


class Config:
    """Configuration class for Telegram Weather Bot."""

    # Telegram Bot Configuration
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
    
    # OpenWeatherMap API Configuration
    # Supports both OPENWEATHER_API_KEY and WEATHER_API_KEY for backward compatibility
    OPENWEATHER_API_KEY: str = os.getenv("OPENWEATHER_API_KEY", "") or os.getenv("WEATHER_API_KEY", "")
    
    # Database Configuration
    DB_PATH: str = os.getenv("DB_PATH", "cities.db")
    
    # API Configuration
    OPENWEATHER_API_URL: str = "https://api.openweathermap.org/data/2.5/forecast"
    OPENWEATHER_UNITS: str = "metric"  # metric, imperial, or kelvin
    OPENWEATHER_LANG: str = "ru"  # Language for weather descriptions
    
    # Telegram API Configuration
    TELEGRAM_API_BASE_URL: str = "https://api.telegram.org/bot"
    TELEGRAM_TIMEOUT: int = 30  # Long polling timeout in seconds
    TELEGRAM_REQUEST_TIMEOUT: int = 35  # HTTP request timeout in seconds
    
    # Weather Forecast Configuration
    FORECAST_HOURS: int = 6  # Number of forecast points to show (each point is 3 hours)
    
    # Network Configuration
    HTTP_TIMEOUT: int = 15  # Timeout for OpenWeatherMap API requests
    
    @classmethod
    def validate(cls) -> None:
        """Validate that all required configuration values are set."""
        if not cls.TELEGRAM_TOKEN:
            raise RuntimeError("Missing required configuration: TELEGRAM_TOKEN")
        if not cls.OPENWEATHER_API_KEY:
            raise RuntimeError("Missing required configuration: OPENWEATHER_API_KEY or WEATHER_API_KEY")
    
    @classmethod
    def get_telegram_token(cls) -> str:
        """Get Telegram bot token."""
        if not cls.TELEGRAM_TOKEN:
            raise RuntimeError("Missing env var: TELEGRAM_TOKEN")
        return cls.TELEGRAM_TOKEN
    
    @classmethod
    def get_openweather_api_key(cls) -> str:
        """Get OpenWeatherMap API key."""
        if not cls.OPENWEATHER_API_KEY:
            raise RuntimeError("Missing env var: OPENWEATHER_API_KEY or WEATHER_API_KEY")
        return cls.OPENWEATHER_API_KEY
    
    @classmethod
    def get_db_path(cls) -> str:
        """Get database file path."""
        return cls.DB_PATH


# Create a singleton instance for easy access
config = Config()
