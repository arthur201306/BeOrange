import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configurações base que servem para todos os ambientes."""
    PROJECT_NAME = "AIDoc Hub"
    VERSION = "V1.0.1"
    CONFIG_SERVER = os.environ.get('CONFIG_DB_SERVER')
    CONFIG_DATABASE = os.environ.get('CONFIG_DB_DATABASE')
    CONFIG_USERNAME = os.environ.get('CONFIG_DB_USERNAME')
    CONFIG_PASSWORD = os.environ.get('CONFIG_DB_PASSWORD')
    CONFIG_TABLE = os.environ.get('CONFIG_DB_TABLE')


class DevelopmentConfig(Config):
    """Configurações para o ambiente de desenvolvimento."""
    DEBUG = True


class TestingConfig(Config):
    """Configurações para o ambiente de testes."""
    TESTING = True
    LOG_SERVER = os.environ.get('TESTING_LOG_DB_SERVER')
    LOG_DATABASE = os.environ.get('TESTING_LOG_DB_DATABASE')
    LOG_USERNAME = os.environ.get('TESTING_LOG_DB_USERNAME')
    LOG_PASSWORD = os.environ.get('TESTING_LOG_DB_PASSWORD')
    LOG_TABLE = os.environ.get('TESTING_LOG_DB_TABLE')


class ProductionConfig(Config):
    """Configurações para o ambiente de produção."""
    DEBUG = False
    TESTING = False
    LOG_SERVER = os.environ.get('LOG_DB_SERVER')
    LOG_DATABASE = os.environ.get('LOG_DB_DATABASE')
    LOG_USERNAME = os.environ.get('LOG_DB_USERNAME')
    LOG_PASSWORD = os.environ.get('LOG_DB_PASSWORD')
    LOG_TABLE = os.environ.get('LOG_DB_TABLE')


config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
