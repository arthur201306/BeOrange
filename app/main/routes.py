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

# Configuração das Etapas do Funil
STAGES_CONFIG: List[Dict[str, str]] = [
    {'id': 'Aguardando retorno', 'title': 'Aguardando retorno', 'color': 'bg-blue-500'},
    {'id': 'Em atendimento', 'title': 'Em atendimento', 'color': 'bg-yellow-500'},
    {'id': 'Reunião', 'title': 'Reunião', 'color': 'bg-purple-500'},
    {'id': 'Em proposta', 'title': 'Em proposta', 'color': 'bg-red-500'},
    {'id': 'Finalizado', 'title': 'Finalizado', 'color': 'bg-green-500'}
]

# Mapa de Cores das Áreas (Tags)
AREAS_COLOR_MAP: Dict[str, str] = {
    'TI': 'text-white bg-indigo-500',
    'Marketing': 'text-white bg-teal-500',
    'Vendas': 'text-white bg-orange-500',
    'Financeiro': 'text-white bg-cyan-500',
    'RH': 'text-white bg-pink-500',
    'default': 'text-white bg-gray-500',
    'TESTE': 'text-white bg-blue-500'
}

# --- Helpers de Blueprint ---

def get_supabase() -> Client:
    """
    Cria ou recupera o cliente Supabase para a requisição atual.
    Armazena no objeto 'g' do Flask.
    """
    if 'supabase' not in g:
        if not url or not key:
            abort(503, "A conexão com o banco de dados (Supabase) não foi inicializada.")
        g.supabase = create_client(url, key)
    return g.supabase

@main_bp.before_request
def check_supabase_connection():
    """
    Hook executado ANTES de CADA rota.
    Verifica se o Supabase pode ser conectado.
    """
    get_supabase() 

def get_layout_template() -> str:
    """Retorna o NOME DO ARQUIVO do template de layout base."""
    return 'layout_sidebar.html' if session.get('layout') == 'sidebar' else 'layout_topbar.html'

# --- Rotas de Página (Views) ---

@main_bp.route('/')
def home():
    return redirect(url_for('main.kanban_board'))

@main_bp.route('/leads')
def kanban_board():
    """ Renderiza o quadro Kanban. (ATUALIZADO PARA M:N) """
    supabase = get_supabase()
    leads_final = []
    error_msg = None
    
    try:
        # 1. A "JUNÇÃO" (JOIN)
        response = supabase.table('clientes').select(
            "id, nome_empresa, nome_contato, etapa, responsavel, created_at, areas(nome)"
        ).order('created_at', desc=True).execute()
        
        leads_raw = response.data

        # 2. A TRANSFORMAÇÃO
        for lead in leads_raw:
            if lead.get('areas') and isinstance(lead['areas'], list):
                lead['areas'] = [area['nome'] for area in lead['areas'] if 'nome' in area]
            else:
                lead['areas'] = []
            leads_final.append(lead)
            
    except Exception as e:
        error_msg = f"Erro ao buscar leads: {e}"

    return render_template(
        "kanban_crm.html", 
        all_leads_json=leads_final, # Passa a lista formatada
        all_stages_json=STAGES_CONFIG,
        areas_colors_json=AREAS_COLOR_MAP, 
        error=error_msg,
        base_template_name=get_layout_template() 
    )

@main_bp.route('/leads/novo', methods=['GET'])
def create_lead_page():
    """ 
    Mostra a PÁGINA com o formulário para criar um novo lead. 
    (VOCÊ AINDA NÃO TEM O TEMPLATE 'create_lead.html')
    """
    supabase = get_supabase()
    
    # Busca todas as áreas para o formulário
    all_areas = []
    try:
        all_areas_response = supabase.table('areas').select("id, nome").execute()
        all_areas = all_areas_response.data
    except Exception as e:
        print(f"Erro ao buscar areas para novo lead: {e}")
        
    return render_template(
        "create_lead.html", # Você precisa criar este arquivo
        all_areas=all_areas,
        all_stages=STAGES_CONFIG,
        base_template_name=get_layout_template(),
        page_title="Criar Novo Lead"
    )

@main_bp.route('/leads/editar/<int:lead_id>')
def edit_lead_page(lead_id):
    """ Mostra a PÁGINA de edição para um lead específico. """
    supabase = get_supabase()
    
    try:
        # Busca o lead específico E suas áreas
        response = supabase.table('clientes').select(
            "*, areas(id, nome)"
        ).eq('id', lead_id).single().execute()
        
        lead = response.data
        print(lead['etapa'])
        if not lead:
            abort(404, "Lead não encontrado")
            
        # Transforma as áreas para facilitar o preenchimento do formulário
        if lead.get('areas') and isinstance(lead['areas'], list):
            # Salva os IDs das áreas que o cliente JÁ POSSUI
            lead['areas_atuais'] = [area['id'] for area in lead['areas']]
        else:
            lead['areas_atuais'] = []

        # Busca TODAS as áreas possíveis para o formulário
        all_areas_response = supabase.table('areas').select("id, nome").execute()
        all_areas = all_areas_response.data
            
    except Exception as e:
        abort(500, f"Erro ao buscar lead: {e}")

    return render_template(
        "edit_lead.html", # Este template você já tem
        lead=lead,
        all_areas=all_areas,
        all_stages=STAGES_CONFIG, # Passa as etapas para o form
        base_template_name=get_layout_template(),
        page_title=f"Editar Lead: {lead.get('nome_empresa')}"
    )

@main_bp.route('/clientes')
def client_list_page():
    """ Renderiza uma lista tabular de todos os clientes. (ATUALIZADO PARA M:N) """
    supabase = get_supabase()
    clientes_final = []
    error_msg = None
    
    try:
        # 1. A "JUNÇÃO" (JOIN)
        response = supabase.table('clientes').select(
            "id, nome_empresa, nome_contato, email, telefone, responsavel, etapa, created_at, areas(nome)"
        ).order('nome_empresa', desc=False).execute()
        
        clientes_raw = response.data

        # 2. A TRANSFORMAÇÃO
        for cliente in clientes_raw:
            if cliente.get('areas') and isinstance(cliente['areas'], list):
                cliente['areas'] = [area['nome'] for area in cliente['areas'] if 'nome' in area]
            else:
                cliente['areas'] = []
            clientes_final.append(cliente)

    except Exception as e:
        error_msg = f"Erro ao buscar clientes: {e}"

    return render_template(
        "clientes_lista.html",
        clientes=clientes_final, # Passa a lista formatada
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
    
    try:
        response = supabase.table('clientes').select("etapa, responsavel, nome_empresa, created_at").order('created_at', desc=True).execute()
        clientes = response.data
    except Exception as e:
        error_msg = f"Erro ao buscar dados do dashboard: {e}"

    dashboard_data = {
        'total_leads': 0,
        'contagem_etapas': {},
        'contagem_responsaveis': [],
        'recentes_leads': []
    }
    if clientes:
        dashboard_data['total_leads'] = len(clientes)
        etapas_dos_clientes = [c.get('etapa') for c in clientes if c.get('etapa')]
        dashboard_data['contagem_etapas'] = Counter(etapas_dos_clientes)
        responsaveis_dos_clientes = [c.get('responsavel') for c in clientes if c.get('responsavel')]
        dashboard_data['contagem_responsaveis'] = Counter(responsaveis_dos_clientes).most_common(5)
        dashboard_data['recentes_leads'] = clientes[:5]

    return render_template(
        "negocios.html", 
        base_template_name=get_layout_template(),
        error=error_msg,
        data=dashboard_data,
        stages_config=STAGES_CONFIG 
    )

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
    """ API para criar um novo lead. (ATUALIZADO PARA M:N) """
    supabase = get_supabase()
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Nenhum dado JSON recebido.'}), 400

    # Pega os NOMES das áreas (ex: ["Vendas", "TI"])
    area_names = data.get('areas', []) 

    # 1. Prepara dados do CLIENTE
    new_lead_data = {
        'nome_contato': data.get('nome_contato'),
        'nome_empresa': data.get('nome_empresa'),
        'email': data.get('email'),
        'telefone': data.get('telefone'),
        'responsavel': data.get('responsavel'),
        'etapa': data.get('etapa', 'Aguardando retorno'),
    }
    
    try:
        # 2. Insere o CLIENTE
        response_cliente = supabase.table('clientes').insert(new_lead_data).execute()
        
        if not response_cliente.data:
            return jsonify({'success': False, 'error': 'Falha ao criar cliente.'}), 500
            
        new_lead = response_cliente.data[0]
        new_lead_id = new_lead['id']
        
        # 3. Processa as ÁREAS
        if area_names:
            # 3a. Busca os IDs das áreas na tabela 'areas'
            response_areas = supabase.table('areas') \
                                     .select('id, nome') \
                                     .in_('nome', area_names) \
                                     .execute()
            
            area_id_map = {area['nome']: area['id'] for area in response_areas.data}

            # 3b. Prepara os dados para a tabela de JUNÇÃO
            junction_data_to_insert = []
            for name in area_names:
                if name in area_id_map:
                    junction_data_to_insert.append({
                        'cliente_id': new_lead_id,
                        'area_id': area_id_map[name]
                    })
            
            # 3c. Insere as relações na tabela 'clientes_areas'
            if junction_data_to_insert:
                supabase.table('clientes_areas').insert(junction_data_to_insert).execute()

        new_lead['areas'] = area_names 
        return jsonify({'success': True, 'lead': new_lead}), 201
            
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
            return jsonify({'success': False, 'error': 'Nenhum dado atualizado (verifique o ID e RLS)'}), 404

    except Exception as e:
        print(f"Erro ao atualizar lead {lead_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# [# CORRIGIDO #] - Esta é a rota que estava duplicada. Agora só há uma.
@main_bp.route('/api/leads/update/<int:lead_id>', methods=['POST'])
def update_lead_action(lead_id):
    """ API para atualizar um lead existente (usado pela página de edição). """
    supabase = get_supabase()
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Nenhum dado JSON recebido.'}), 400

    # Pega os IDs das áreas (ex: [1, 3])
    area_ids = data.get('areas', [])

    # 1. Prepara dados do CLIENTE
    lead_update_data = {
        'nome_contato': data.get('nome_contato'),
        'nome_empresa': data.get('nome_empresa'),
        'email': data.get('email'),
        'telefone': data.get('telefone'),
        'responsavel': data.get('responsavel'),
        'etapa': data.get('etapa'),
    }

    try:
        # 2. Atualiza os dados principais na tabela 'clientes'
        supabase.table('clientes').update(lead_update_data).eq('id', lead_id).execute()
        
        # 3. Sincroniza as ÁREAS (a parte M:N)
        # 3a. Deleta TODAS as associações antigas deste cliente
        supabase.table('clientes_areas').delete().eq('cliente_id', lead_id).execute()

        # 3b. Insere as novas associações (se houver)
        if area_ids:
            junction_data_to_insert = [
                {'cliente_id': lead_id, 'area_id': area_id} for area_id in area_ids
            ]
            supabase.table('clientes_areas').insert(junction_data_to_insert).execute()

        return jsonify({'success': True}), 200
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
@main_bp.route('/areas')
def list_areas_page():
    """ Renderiza a página para ver e criar novas Áreas. """
    supabase = get_supabase()
    all_areas = []
    error_msg = None
    
    try:
        response = supabase.table('areas').select("*").order('nome').execute()
        all_areas = response.data
    except Exception as e:
        error_msg = f"Erro ao buscar áreas: {e}"

    return render_template(
        "list_areas.html", # <-- Novo template que vamos criar
        all_areas=all_areas,
        error=error_msg,
        base_template_name=get_layout_template(),
        page_title="Gerenciar Áreas"
    )

@main_bp.route('/api/areas/create', methods=['POST'])
def create_area_action():
    """ API para criar uma nova área. """
    supabase = get_supabase()
    data = request.get_json()
    
    if not data or not data.get('nome'):
        return jsonify({'success': False, 'error': 'Nome da área é obrigatório.'}), 400

    area_nome = data.get('nome')

    try:
        # Verifica se a área já existe
        existing = supabase.table('areas').select('id').eq('nome', area_nome).execute()
        if existing.data:
            return jsonify({'success': False, 'error': 'Uma área com este nome já existe.'}), 409

        # Insere a nova área
        response = supabase.table('areas').insert({'nome': area_nome}).execute()
        
        if response.data:
            return jsonify({'success': True, 'area': response.data[0]}), 201
        else:
            return jsonify({'success': False, 'error': 'Falha ao inserir dados.'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500