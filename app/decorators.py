from flask import url_for, redirect
from app.main.services import verify_application_version, verify_blocklist
from functools import wraps


def verify_application_status(f):
    """
    Um decorator que verifica o status da aplicação antes de executar uma rota.
    Ele checa duas coisas, nesta ordem:
    1. Se o usuário atual está na blocklist.
    2. Se a versão da aplicação local bate com a do banco de dados.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if verify_blocklist()[0] == True:
            return redirect(url_for('main.blocklist'))

        if verify_application_version()[0] == False:
            return redirect(url_for('main.version_mismatch'))
        return f(*args, **kwargs)

    return decorated_function
