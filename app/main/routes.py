import os
from flask import (
    render_template, Blueprint, request, redirect, url_for, 
    jsonify, session, abort, g
)
from supabase import create_client, Client
from dotenv import load_dotenv
from typing import List, Dict, Any
from collections import Counter # Para o dashboard

# --- Configuração do Blueprint ---
main_bp = Blueprint('main', __name__, template_folder='templates')

# --- Carregar .env e Conectar ao Supabase ---
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("Erro Crítico: Variáveis SUPABASE_URL ou SUPABASE_KEY não encontradas.")
    # Em um app real, você pode querer lançar uma exceção aqui

# --- Constantes de Configuração ---

# Colunas para o Kanban (incluindo as que o card precisa)
KANBAN_COLUMNS: str = "id, nome_empresa, nome_contato, etapa, responsavel, created_at, areas"

# Colunas para a lista de clientes
CLIENT_LIST_COLUMNS: str = "id, nome_empresa, nome_contato, email, telefone, responsavel, etapa, created_at, areas"

# Configuração das Etapas do Funil
STAGES_CONFIG: List[Dict[str, str]] = [
    {'id': 'Aguardando retorno', 'title': 'Aguardando retorno', 'color': 'bg-blue-500'},
    {'id': 'Em atendimento', 'title': 'Em atendimento', 'color': 'bg-yellow-500'},
    {'id': 'Reuniao', 'title': 'Reunião', 'color': 'bg-purple-500'},
    {'id': 'Em proposta', 'title': 'Em proposta', 'color': 'bg-red-500'},
    {'id': 'Finalizado', 'title': 'Finalizado', 'color': 'bg-green-500'}
]

# Mapa de Cores das Áreas (Tags)
AREAS_COLOR_MAP: Dict[str, str] = {
    'TI': 'text-blue-800 bg-blue-100',
    'Marketing': 'text-green-800 bg-green-100',
    'Vendas': 'text-yellow-800 bg-yellow-100',
    'Financeiro': 'text-indigo-800 bg-indigo-100',
    'RH': 'text-pink-800 bg-pink-100',
    # Uma cor "padrão" para áreas não mapeadas
    'default': 'text-gray-800 bg-gray-100'
}

# --- Helpers de Blueprint ---

def get_supabase() -> Client:
    """
    Cria ou recupera o cliente Supabase para a requisição atual.
    Armazena no objeto 'g' do Flask.
    """
    if 'supabase' not in g:
        if not url or not key:
            # 503 Service Unavailable
            abort(503, "A conexão com o banco de dados (Supabase) não foi inicializada.")
            
        g.supabase = create_client(url, key)
        
    return g.supabase

@main_bp.before_request
def check_supabase_connection():
    """
    Hook executado ANTES de CADA rota.
    Verifica se o Supabase pode ser conectado.
    """
    get_supabase() # Isso vai popular g.supabase ou dar abort(503)

def get_layout_template() -> str:
    """Retorna o NOME DO ARQUIVO do template de layout base."""
    return 'layout_sidebar.html' if session.get('layout') == 'sidebar' else 'layout_topbar.html'

# --- Rotas de Página (Views) ---

@main_bp.route('/')
def home():
    return redirect(url_for('main.kanban_board'))

@main_bp.route('/leads')
def kanban_board():
    """ Renderiza o quadro Kanban. """
    supabase = get_supabase()
    leads = []
    error_msg = None
    
    try:
        response = supabase.table('clientes').select(KANBAN_COLUMNS).order('created_at', desc=True).execute()
        leads = response.data
    except Exception as e:
        error_msg = f"Erro ao buscar leads: {e}"

    return render_template(
        "kanban_crm.html", 
        all_leads_json=leads, 
        all_stages_json=STAGES_CONFIG,
        areas_colors_json=AREAS_COLOR_MAP, # Envia o mapa de cores
        error=error_msg,
        base_template_name=get_layout_template() 
    )

@main_bp.route('/leads/novo', methods=['GET'])
def create_lead_page():
    """ Mostra a PÁGINA com o formulário para criar um novo lead. """
    return render_template(
        "create_lead.html", # Você precisa criar este arquivo
        base_template_name=get_layout_template(),
        page_title="Criar Novo Lead"
    )

@main_bp.route('/clientes')
def client_list_page():
    """ Renderiza uma lista tabular de todos os clientes. """
    supabase = get_supabase()
    clientes = []
    error_msg = None
    
    try:
        response = supabase.table('clientes').select(CLIENT_LIST_COLUMNS).order('nome_empresa', desc=False).execute()
        clientes = response.data
    except Exception as e:
        error_msg = f"Erro ao buscar clientes: {e}"

    return render_template(
        "clientes_lista.html",
        clientes=clientes,
        error=error_msg,
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
    """Renderiza a página Central de Negócios (Dashboard)."""
    supabase = get_supabase()
    
    clientes = []
    error_msg = None
    
    # 1. Obter os dados
    try:
        # Pedimos os dados que importam para o dashboard
        response = supabase.table('clientes').select("etapa, responsavel, nome_empresa, created_at").order('created_at', desc=True).execute()
        clientes = response.data
    except Exception as e:
        error_msg = f"Erro ao buscar dados do dashboard: {e}"

    # 2. Processar os dados para o Dashboard
    dashboard_data = {
        'total_leads': 0,
        'contagem_etapas': {},
        'contagem_responsaveis': [],
        'recentes_leads': []
    }

    if clientes:
        dashboard_data['total_leads'] = len(clientes)
        
        # Contar leads por etapa
        etapas_dos_clientes = [c.get('etapa') for c in clientes if c.get('etapa')]
        dashboard_data['contagem_etapas'] = Counter(etapas_dos_clientes)
        
        # Contar leads por responsável (e pegar os top 5)
        responsaveis_dos_clientes = [c.get('responsavel') for c in clientes if c.get('responsavel')]
        dashboard_data['contagem_responsaveis'] = Counter(responsaveis_dos_clientes).most_common(5)

        # Pegar os 5 leads mais recentes
        dashboard_data['recentes_leads'] = clientes[:5]

    return render_template(
        "negocios.html", 
        base_template_name=get_layout_template(),
        error=error_msg,
        data=dashboard_data,
        stages_config=STAGES_CONFIG # Passa a config de etapas para o template
    )

@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    """ Rota de login (sem layout principal) """
    if request.method == 'GET':
        return render_template("login.html", base_template_name='base.html') 
    # (Lógica de POST login)
    
# --- Rotas de Controle ---

@main_bp.route('/set-layout/<layout_name>')
def set_layout(layout_name):
    """ Salva a preferência de layout do usuário na sessão. """
    if layout_name in ['topbar', 'sidebar']:
        session['layout'] = layout_name
    return redirect(request.referrer or url_for('main.home'))

# --- Rotas de API ---

@main_bp.route('/api/leads/create', methods=['POST'])
def create_lead_action():
    supabase = get_supabase()
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Nenhum dado JSON recebido.'}), 400

    new_lead_data = {
        'nome_contato': data.get('nome_contato'),
        'nome_empresa': data.get('nome_empresa'),
        'email': data.get('email'),
        'telefone': data.get('telefone'),
        'responsavel': data.get('responsavel'),
        'etapa': data.get('etapa', 'Aguardando retorno'),
        'areas': data.get('areas', []) # Aceita um array de áreas
    }
    
    try:
        response = supabase.table('clientes').insert(new_lead_data).execute()
        
        if response.data:
            return jsonify({'success': True, 'lead': response.data[0]}), 201
        else:
            return jsonify({'success': False, 'error': 'Falha ao inserir dados.'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/update_stage', methods=['POST'])
def update_lead_stage():
    """ API para atualizar a etapa de um lead (drag-and-drop). """
    supabase = get_supabase()
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
            return jsonify({'success': True})
        else:
            # Isso pode acontecer se o RLS bloquear ou o ID estiver errado
            return jsonify({'success': False, 'error': 'Nenhum dado atualizado (verifique o ID e RLS)'}), 404

    except Exception as e:
        print(f"Erro ao atualizar lead {lead_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500