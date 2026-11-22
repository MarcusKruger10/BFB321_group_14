import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "pharmacy_tracker")
    DEBUG = False
    TESTING = False


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    DB_NAME = os.getenv("TEST_DB_NAME", "pharmacy_tracker_test")


class ProductionConfig(Config):
    pass


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name=None):
    """Return the config class for FLASK_ENV (default: development)."""
    return config_by_name.get(name or os.getenv("FLASK_ENV", "development"), DevelopmentConfig)