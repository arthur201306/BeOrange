from flask import Flask
from .main import routes as main_routes
import os
#from .config import config_by_name


def create_app(config_name='default'):
    """Cria e configura uma instância da aplicação Flask."""

    app = Flask(__name__, instance_relative_config=True)
    #app.config.from_object(config_by_name[config_name])
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')

    app.register_blueprint(main_routes.main_bp)

    return app
