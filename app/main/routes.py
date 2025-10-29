from flask import render_template, Blueprint, request, redirect, url_for

# Cria o Blueprint 'main'
main_bp = Blueprint('main', __name__, template_folder='templates')


@main_bp.route('/')
def home():
    """Redireciona a rota base para a página de Leads."""
    return redirect(url_for('main.kanban_board'))

@main_bp.route('/leads')
def kanban_board():
    """Renderiza a página principal do quadro Kanban (Gestão de Leads)."""
    return render_template("kanban_crm.html")

@main_bp.route('/atendimentos')
def atendimentos_page():
    """Renderiza a página de Atendimentos."""
    return render_template("atendimentos.html")

@main_bp.route('/negocios')
def negocios_page():
    """Renderiza a página Central de Negócios."""
    return render_template("negocios.html")

@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Rota de login (atualmente só renderiza o template GET)
    """
    if request.method == 'GET':
        return render_template("login.html") # Assumindo que você tem um template login.html
