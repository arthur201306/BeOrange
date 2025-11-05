import os
from flask import (
    render_template, Blueprint, request, redirect, url_for, jsonify, session
)
from supabase import create_client, Client
from dotenv import load_dotenv

# --- Configuração do Blueprint ---
main_bp = Blueprint('main', __name__, template_folder='templates')

# --- Carregar .env e Conectar ao Supabase ---
# Carrega .env da pasta raiz (acima da pasta 'app')
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("Erro Crítico: Variáveis SUPABASE_URL ou SUPABASE_KEY não encontradas.")
    supabase = None
else:
    supabase: Client = create_client(url, key)

# --- Configuração das Colunas do Kanban ---
STAGES_CONFIG = [
    {'id': 'Aguardando retorno', 'title': 'Aguardando retorno', 'color': 'bg-blue-500'},
    {'id': 'Em atendimento', 'title': 'Em atendimento', 'color': 'bg-yellow-500'},
    {'id': 'Reuniao', 'title': 'Reunião', 'color': 'bg-purple-500'},
    {'id': 'Em proposta', 'title': 'Em proposta', 'color': 'bg-red-500'},
    {'id': 'Finalizado', 'title': 'Finalizado', 'color': 'bg-green-500'}
]

# --- Função Helper de Layout (Atualizada) ---
def get_layout_template():
    """Retorna o NOME DO ARQUIVO do template de layout base."""
    layout_choice = session.get('layout', 'topbar') # Padrão 'topbar'
    if layout_choice == 'sidebar':
        return 'layout_sidebar.html'
    return 'layout_topbar.html'

# --- Rotas Principais (Atualizadas) ---

@main_bp.route('/')
def home():
    return redirect(url_for('main.kanban_board'))

@main_bp.route('/leads')
def kanban_board():
    """ Renderiza o quadro Kanban. """
    leads = []
    error_msg = None
    
    if not supabase:
        error_msg = "Conexão com o Supabase falhou."
    else:
        try:
            response = supabase.table('clientes').select('*').order('created_at', desc=True).execute()
            leads = response.data
        except Exception as e:
            error_msg = f"Erro ao buscar leads: {e}"

    return render_template(
        "kanban_crm.html", 
        all_leads_json=leads, 
        all_stages_json=STAGES_CONFIG,
        error=error_msg,
        # Passa o NOME DO ARQUIVO de layout correto
        base_template_name=get_layout_template() 
    )

@main_bp.route('/clientes')
def client_list_page():
    """ Renderiza uma lista tabular de todos os clientes. """
    clientes = []
    error_msg = None
    
    if not supabase:
        error_msg = "Conexão com o Supabase falhou."
    else:
        try:
            response = supabase.table('clientes').select('*').order('nome', desc=False).execute()
            clientes = response.data
        except Exception as e:
            error_msg = f"Erro ao buscar clientes: {e}"

    return render_template(
        "clientes_lista.html",
        clientes=clientes,
        error=error_msg,
        # Passa o NOME DO ARQUIVO de layout
        base_template_name=get_layout_template()
    )

@main_bp.route('/atendimentos')
def atendimentos_page():
    """Renderiza a página de Atendimentos."""
    return render_template(
        "atendimentos.html", 
        base_template_name=get_layout_template()
    )

@main_bp.route('/negocios')
def negocios_page():
    """Renderiza a página Central de Negócios."""
    return render_template(
        "negocios.html", 
        base_template_name=get_layout_template()
    )

@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    """ Rota de login (sem layout principal) """
    if request.method == 'GET':
        # Passa 'base.html' para não ter NENHUM layout (topbar/sidebar)
        return render_template("login.html", base_template_name='base.html') 
    # (Lógica de POST login)
    
# --- Rota de Controle de Layout ---
@main_bp.route('/set-layout/<layout_name>')
def set_layout(layout_name):
    """ Salva a preferência de layout do usuário na sessão. """
    if layout_name in ['topbar', 'sidebar']:
        session['layout'] = layout_name
    # Redireciona de volta para a página de onde o usuário veio
    return redirect(request.referrer or url_for('main.home'))

# --- Rota da API para o Kanban ---
@main_bp.route('/api/update_stage', methods=['POST'])
def update_lead_stage():
    """ API para atualizar a etapa de um lead (drag-and-drop). """
    if not supabase:
        return jsonify({'success': False, 'error': 'Conexão com Supabase não inicializada'}), 500
    
    data = request.get_json()
    lead_id = data.get('lead_id')
    new_stage = data.get('new_stage')
    
    if not lead_id or not new_stage:
        return jsonify({'success': False, 'error': 'ID do lead ou nova etapa ausentes'}), 400
        
    try:
        response = supabase.table('clientes') \
            .update({'etapa': new_stage}) \
            .eq('id', lead_id) \
            .execute()
            
        if response.data:
            # Correção do TypeError: Apenas retorne o sucesso.
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Nenhum dado atualizado, verifique o ID e as permissões (RLS)'}), 404

    except Exception as e:
        print(f"Erro ao atualizar lead {lead_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500