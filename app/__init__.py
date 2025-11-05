from flask import Flask
#from .config import config_by_name


def create_app(config_name='default'):
    """Cria e configura uma instância da aplicação Flask."""

    app = Flask(__name__, instance_relative_config=True)
    #app.config.from_object(config_by_name[config_name])

    from .main import routes as main_routes


    app.register_blueprint(main_routes.main_bp)

    return app
