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
    {'id': 'aguardando retorno', 'title': 'Aguardando retorno', 'color': 'bg-blue-500'},
    {'id': 'em atendimento', 'title': 'Em atendimento', 'color': 'bg-yellow-500'},
    {'id': 'reunião', 'title': 'Reunião', 'color': 'bg-purple-500'},
    {'id': 'em proposta', 'title': 'Em proposta', 'color': 'bg-red-500'},
    {'id': 'finalizado', 'title': 'Finalizado', 'color': 'bg-green-500'}
]

STAGES_CONFIG_POS_TRANSACTION: List[Dict[str, str]] = [
    {'id': 'Entrega Realizada', 'title': 'Entrega Realizada', 'color': 'bg-blue-500'},
    {'id': 'Aguardando Feedback', 'title': 'Aguardando Feedback', 'color': 'bg-yellow-500'},
    {'id': 'Feedback Recebido', 'title': 'Feedback Recebido', 'color': 'bg-purple-500'},
    {'id': 'Suporte', 'title': 'Suporte', 'color': 'bg-red-500'},
    {'id': 'Possível Upsell', 'title': 'Possível Upsell', 'color': 'bg-orange-500'},
    {'id': 'Finalizado pós-venda', 'title': 'Finalizado pós-venda', 'color': 'bg-green-500'}
]


# Mapa de Cores das Áreas (Tags)
AREAS_COLOR_MAP: Dict[str, str] = {
    'TI': 'text-white bg-indigo-500',
    'Marketing': 'text-white bg-teal-500',
    'Vendas': 'text-white bg-orange-500',
    'Financeiro': 'text-white bg-cyan-500',
    'RH': 'text-white bg-pink-500',
    'default': 'text-white bg-gray-500'
}

# --- Helpers de Blueprint ---
def get_employees_map(supabase: Client) -> Dict[int, str]:
    """ Busca todos os funcionários e retorna um mapa {id: nome} """
    try:
        response = supabase.table('funcionarios').select("id, nome").execute()
        return {emp['id']: emp['nome'] for emp in response.data}
    except Exception as e:
        print(f"Erro ao buscar mapa de funcionários: {e}")
        return {}


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
            "id, nome_empresa, nome_contato, etapa, responsavel(id, nome), created_at, areas(nome)"
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
    """Mostra a página com o formulário para criar um novo lead."""
    supabase = get_supabase()
    
    # Busca todas as áreas para o formulário
    all_areas = []
    try:
        all_areas_response = supabase.table('areas').select("id, nome").execute()
        all_areas = all_areas_response.data
    except Exception as e:
        print(f"Erro ao buscar areas para novo lead: {e}")

    # --- BUSCA FUNCIONÁRIOS ---
    all_employees = []
    try:
        employees_response = supabase.table('funcionarios').select("id, nome").execute()
        all_employees = employees_response.data
    except Exception as e:
        print(f"Erro ao buscar funcionários: {e}")

    return render_template(
        "create_lead.html",
        all_areas=all_areas,
        all_stages=STAGES_CONFIG,
        all_employees=all_employees,  # ⬅️ envia a lista de funcionários
        base_template_name=get_layout_template(),
        page_title="Criar Novo Lead"
    )

@main_bp.route('/leads/editar/<int:lead_id>')
def edit_lead_page(lead_id):
    """Mostra a página de edição para um lead específico."""
    supabase = get_supabase()
    
    try:
        # Busca o lead específico E suas áreas
        response = supabase.table('clientes').select(
            "*, responsavel(id,nome), areas(id, nome)"
        ).eq('id', lead_id).single().execute()
        
        lead = response.data
        if not lead:
            abort(404, "Lead não encontrado")
            
        # Transformar áreas existentes para preencher o formulário
        if lead.get('areas') and isinstance(lead['areas'], list):
            lead['areas_atuais'] = [area['id'] for area in lead['areas']]
        else:
            lead['areas_atuais'] = []

        # Busca TODAS as áreas possíveis para o formulário
        all_areas_response = supabase.table('areas').select("id, nome").execute()
        all_areas = all_areas_response.data

        # --- BUSCA FUNCIONÁRIOS ---
        all_employees = []
        try:
            employees_response = supabase.table('funcionarios').select("id, nome").execute()
            all_employees = employees_response.data
        except Exception as e:
            print(f"Erro ao buscar funcionários: {e}")
            
    except Exception as e:
        abort(500, f"Erro ao buscar lead: {e}")

    return render_template(
        "edit_lead.html",
        lead=lead,
        all_areas=all_areas,
        all_stages=STAGES_CONFIG,
        all_employees=all_employees,  # ⬅️ envia a lista de funcionários
        base_template_name=get_layout_template(),
        page_title=f"Editar Lead: {lead.get('nome_empresa')}"
    )

@main_bp.route('/api/leads/create', methods=['POST'])
def create_lead_action():
    """ API para criar um novo lead com áreas e funcionário responsável. """
    supabase = get_supabase()
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Nenhum dado JSON recebido.'}), 400

    area_names = data.get('areas', [])
    responsavel_id = data.get('responsavel')

    try:
        # --- Valida o funcionário ---
        if responsavel_id:
            resp_func = supabase.table('funcionarios').select('id, nome').eq('id', responsavel_id).single().execute()
            if not resp_func.data:
                return jsonify({'success': False, 'error': 'Funcionário responsável não encontrado.'}), 400
            responsavel_nome = resp_func.data['nome']
        else:
            responsavel_nome = None

        # --- Prepara dados do cliente ---
        new_lead_data = {
            'nome_contato': data.get('nome_contato'),
            'nome_empresa': data.get('nome_empresa'),
            'email': data.get('email'),
            'telefone': data.get('telefone'),
            'responsavel': responsavel_id,
            'etapa': data.get('etapa', 'Aguardando retorno'),
        }

        # --- Insere o cliente ---
        response_cliente = supabase.table('clientes').insert(new_lead_data).execute()
        if not response_cliente.data:
            return jsonify({'success': False, 'error': 'Falha ao criar cliente.'}), 500

        new_lead = response_cliente.data[0]
        new_lead_id = new_lead['id']

        # --- Processa as Áreas (M:N) ---
        if area_names:
            response_areas = supabase.table('areas').select('id, nome').in_('nome', area_names).execute()
            area_id_map = {area['nome']: area['id'] for area in response_areas.data}

            junction_data_to_insert = [
                {'cliente_id': new_lead_id, 'area_id': area_id_map[name]}
                for name in area_names if name in area_id_map
            ]

            if junction_data_to_insert:
                supabase.table('clientes_areas').insert(junction_data_to_insert).execute()

        new_lead['areas'] = area_names
        new_lead['responsavel_nome'] = responsavel_nome  # retorna também o nome do funcionário

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
    
@main_bp.route('/move_to_post_sale', methods=['POST'])
def move_to_post_sale():
    print("Recebida requisição para mover lead para Pós-Venda")
    data = request.get_json()
    lead_id = data.get('lead_id')
    supabase = get_supabase()
    
    if not lead_id:
        return jsonify({"success": False, "error": "ID do lead não fornecido"}), 400

    try:
        # 1. BUSCAR lead original (Tabela: clientes)
        # Selecionamos todas as colunas que coincidem com clientes_posvenda
        lead_response = supabase.table('clientes').select('nome_empresa, nome_contato, email, telefone, responsavel, created_at, etapa').eq('id', lead_id).single().execute()
        area_response = supabase.table('clientes_areas').select('area_id').eq('cliente_id', lead_id).execute()
        lead_data = lead_response.data
        
        if not lead_data:
             return jsonify({"success": False, "error": "Lead não encontrado para transição"}), 404

        # 2. PREPARAR DADOS para Inserção (Tabela: clientes_posvenda)
        
        # Como as colunas são as mesmas (etapa, nome_empresa, etc.), 
        # podemos reutilizar a maioria dos dados e apenas ajustar o essencial.
        new_client_data = {
            'nome_empresa': lead_data.get('nome_empresa'),
            'nome_contato': lead_data.get('nome_contato'),
            'email': lead_data.get('email'),
            'telefone': lead_data.get('telefone'),
            'responsavel': lead_data.get('responsavel'), # Assumindo que este é o ID do responsável
            
            # ATENÇÃO: Define a primeira etapa do Pós-Venda
            'etapa': 'Entrega Realizada', 
            
            # Opcional: Manter o created_at original ou adicionar uma data_transicao
            # 'created_at': lead_data.get('created_at') 
        }

        
        # 3. INSERIR na tabela clientes_posvenda
        result = supabase.table('clientes_posvenda').insert(new_client_data).execute()
        new_client_id = result.data[0]['id'] 
        
        # 4. AÇÃO NO LEAD ORIGINAL (Tabela: clientes)
        # Apenas atualiza a etapa para "Arquivado" para que o backend possa filtrar futuramente.
        # Por enquanto, o front-end já o remove.
        supabase.table('clientes').update({'etapa': 'Venda Concluída - ARQUIVADO'}).eq('id', lead_id).execute()

        areas_to_insert = [
            {
                'cliente_posvenda_id': new_client_id,
                'area_id': area['area_id']
            }
            # Percorre os IDs de área do lead original (area_response.data)
            for area in area_response.data 
        ]

        supabase.table('clientes_posvenda_areas').insert(areas_to_insert).execute()

        # Não se preocupe com o filtro do /leads por enquanto, apenas garanta que o cliente
        # saiba que o lead não está mais no Kanban ativo.
        
        return jsonify({"success": True, "new_client_id": new_client_id})

    except Exception as e:
        print(f"Erro ao mover para Pós-Venda: {e}")
        return jsonify({"success": False, "error": f"Falha na transição: {str(e)}"}), 500

# ----------------------------------------------------------------------------------------------------------------------------------------------------- #
@main_bp.route('/posvenda')
def kanban_board_posvenda():
    supabase = get_supabase()
    leads_final = []
    error_msg = None
    
    try:
        # 1. CORREÇÃO: Usar o nome da coluna correto da tabela 'clientes_posvenda'
        response = supabase.table('clientes_posvenda').select(
            "id, nome_empresa, nome_contato, etapa, responsavel(id, nome), created_at, areas(nome)"
        ).order('created_at', desc=True).execute()
        
        leads_raw = response.data

        # 2. TRANSFORMAÇÃO E RENOMEAÇÃO para compatibilidade com o JS
        for lead in leads_raw:
            
            # Renomeia 'etapa' para 'etapa' no objeto final para o Kanban JS
            if 'etapa' in lead:
                # Usa .pop() para mover o valor e remover a chave antiga
                lead['etapa'] = lead.pop('etapa')
            
            # Formatação das áreas (como já estava)
            if lead.get('areas') and isinstance(lead['areas'], list):
                lead['areas'] = [area['nome'] for area in lead['areas'] if 'nome' in area]
            else:
                lead['areas'] = []
            
            leads_final.append(lead)
            
    except Exception as e:
        error_msg = f"Erro ao buscar clientes de Pós-Venda: {e}"
        leads_final = [] 

    # 3. PASSAGEM SEGURA de variáveis de contexto
    return render_template(
        "kanban_crm_pos_venda.html", 
        all_leads_json=leads_final, 
        # Garante que as constantes globais sejam passadas, usando um valor padrão se não existirem
        all_stages_json=globals().get('STAGES_CONFIG_POS_TRANSACTION', []),
        areas_colors_json=globals().get('AREAS_COLOR_MAP', {}), 
        error=error_msg,
        base_template_name=globals().get('get_layout_template', lambda: "layout_sidebar.html")()
    )

@main_bp.route('/api/posvenda/update_stage', methods=['POST'])
def update_post_sale_stage():
    supabase = get_supabase()
    data = request.get_json()
    lead_id = data.get('client_id')
    new_stage = data.get('new_stage')

    print(f"Recebida requisição para atualizar etapa Pós-Venda {data} ")
    print(f"Atualizando lead Pós-Venda {lead_id} para etapa {new_stage}")
    
    if not lead_id or not new_stage:
        return jsonify({'success': False, 'error': 'ID do lead ou nova etapa ausentes'}), 400
        
    try:
        response = supabase.table('clientes_posvenda') \
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

@main_bp.route('/pos_venda/editar/<int:lead_id>')
def edit_posvenda_page(lead_id):
    """Mostra a página de edição para um lead específico."""
    supabase = get_supabase()
    
    try:
        # Busca o lead específico E suas áreas
        response = supabase.table('clientes_posvenda').select(
            "*, responsavel(id,nome), areas(id, nome)"
        ).eq('id', lead_id).single().execute()
        
        lead = response.data
        if not lead:
            abort(404, "Lead não encontrado")
            
        # Transformar áreas existentes para preencher o formulário
        if lead.get('areas') and isinstance(lead['areas'], list):
            lead['areas_atuais'] = [area['id'] for area in lead['areas']]
        else:
            lead['areas_atuais'] = []

        # Busca TODAS as áreas possíveis para o formulário
        all_areas_response = supabase.table('areas').select("id, nome").execute()
        all_areas = all_areas_response.data

        # --- BUSCA FUNCIONÁRIOS ---
        all_employees = []
        try:
            employees_response = supabase.table('funcionarios').select("id, nome").execute()
            all_employees = employees_response.data
        except Exception as e:
            print(f"Erro ao buscar funcionários: {e}")
            
    except Exception as e:
        abort(500, f"Erro ao buscar lead: {e}")

    return render_template(
        "edit_lead_posvenda.html",
        lead=lead,
        all_areas=all_areas,
        all_stages=STAGES_CONFIG_POS_TRANSACTION,
        all_employees=all_employees,  # ⬅️ envia a lista de funcionários
        base_template_name=get_layout_template(),
        page_title=f"Editar Lead: {lead.get('nome_empresa')}"
    )

@main_bp.route('/api/posvenda/update/<int:lead_id>', methods=['POST'])
def update_posvenda_action(lead_id):
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
        supabase.table('clientes_posvenda').update(lead_update_data).eq('id', lead_id).execute()
        
        # 3. Sincroniza as ÁREAS (a parte M:N)
        # 3a. Deleta TODAS as associações antigas deste cliente
        supabase.table('clientes_posvenda_areas').delete().eq('cliente_id', lead_id).execute()

        # 3b. Insere as novas associações (se houver)
        if area_ids:
            junction_data_to_insert = [
                {'cliente_id': lead_id, 'area_id': area_id} for area_id in area_ids
            ]
            supabase.table('clientes_posvenda_areas').insert(junction_data_to_insert).execute()

        return jsonify({'success': True}), 200
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def fetch_history_data(supabase: Client, table_name: str, id_column: str, cliente_id: int) -> List[Dict[str, Any]]:
    """ Busca os registros de histórico em uma tabela específica para um dado cliente. """
    try:
        # Busca ordenando pela data da ação mais recente primeiro
        response = supabase.table(table_name).select(
           "*"
        ).eq(id_column, cliente_id).execute()
        
        return response.data
    except Exception as e:
        print(f"Erro ao buscar histórico em {table_name}: {e}")
        return []

@main_bp.route('/historico/<string:tipo_cliente>/<int:cliente_id>')
def view_history(tipo_cliente: str, cliente_id: int):
    """ 
    Renderiza a página de histórico de auditoria para um cliente (Lead ou Pós-Venda).
    
    tipo_cliente deve ser 'lead' ou 'posvenda'.
    """
    supabase = get_supabase()
    history_data = []
    page_title = "Histórico de Ações"
    
    if tipo_cliente == 'lead':
        # ID do Lead na tabela 'clientes' e 'historico_acoes' é 'lead_id'
        history_data = fetch_history_data(supabase, 'historico_acoes', 'lead_id', cliente_id)
        

    elif tipo_cliente == 'posvenda':
        # ID do Cliente na tabela 'clientes_posvenda' e 'historico_posvenda' é 'cliente_id'
        history_data = fetch_history_data(supabase, 'historico_posvenda', 'cliente_id', cliente_id)
        page_title = f"Histórico do Cliente Pós-Venda ID {cliente_id}"
             
    else:
        abort(404, "Tipo de cliente inválido. Use 'lead' ou 'posvenda'.")

    return render_template(
        'history_view.html',
        page_title=page_title,
        history_data=history_data, # ESTA VARIÁVEL PRECISA CONTER OS DADOS
    )


# ----------------------------------------------------------------------------------------------------------------------------------------------------- #

@main_bp.route('/clientes')
def client_list_page():
    """ 
    Renderiza uma lista tabular unificada de Leads (clientes) e Clientes de Pós-Venda.
    """
    supabase = get_supabase()
    clientes_final = []
    error_msg = None
    
    # 1. Obter mapa de funcionários (para mostrar o nome ao invés do ID)
    employee_map = get_employees_map(supabase)

    try:
        # --- BUSCA 1: LEADS (Tabela 'clientes') ---
        # Note que aqui não podemos usar responsavel(id, nome), por isso usamos o employee_map
        response_leads = supabase.table('clientes').select(
            "id, nome_empresa, nome_contato, email, telefone, responsavel, etapa, created_at, areas(nome)"
        ).order('nome_empresa', desc=False).neq('etapa', 'Venda Concluída - ARQUIVADO').execute()
        
        leads_raw = response_leads.data

        # --- BUSCA 2: CLIENTES PÓS-VENDA (Tabela 'clientes_posvenda') ---
        response_posvenda = supabase.table('clientes_posvenda').select(
            "id, nome_empresa, nome_contato, email, telefone, responsavel, etapa, created_at, areas(nome)"
        ).order('nome_empresa', desc=False).execute()
        
        posvenda_raw = response_posvenda.data

        # 2. TRANSFORMAÇÃO E UNIFICAÇÃO
        clientes_unificados_raw = []
        
        # Processa Leads
        for cliente in leads_raw:
            cliente['tipo'] = 'Lead'
            clientes_unificados_raw.append(cliente)
            
        # Processa Pós-Venda
        for cliente in posvenda_raw:
            cliente['tipo'] = 'Pós-Venda'
            clientes_unificados_raw.append(cliente)
            
        # Formata os dados unificados
        for cliente in clientes_unificados_raw:
            # Formata áreas
            if cliente.get('areas') and isinstance(cliente['areas'], list):
                cliente['areas'] = [area['nome'] for area in cliente['areas'] if 'nome' in area]
            else:
                cliente['areas'] = []
            
            # Adiciona o nome do responsável
            responsavel_id = cliente.get('responsavel')
            cliente['responsavel_nome'] = employee_map.get(responsavel_id) if responsavel_id else 'N/A'

            clientes_final.append(cliente)

    except Exception as e:
        error_msg = f"Erro ao buscar clientes: {e}"

    return render_template(
        "clientes_lista.html",
        clientes=clientes_final, 
        error=error_msg,
        # É ESSENCIAL passar o mapa de cores para o template formatar as tags
        areas_colors_json=globals().get('AREAS_COLOR_MAP', {}),
        base_template_name=get_layout_template()
    )

# ----------------------------------------------------------------------------------------------------------------------------------------------------- #
# Seu arquivo main/routes.py

@main_bp.route('/negocios')
def negocios_page():
    """Renderiza a página Central de Negócios (Dashboard) com métricas de Leads e Pós-Venda."""
    supabase = get_supabase()
    clientes_unificados = []
    error_msg = None
    
    # 1. BUSCAR MAPA DE FUNCIONÁRIOS
    # Necessário para converter o ID do responsável para o nome (na lista de recentes e contagem)
    employee_map = get_employees_map(supabase)

    try:
        # --- BUSCA 1: LEADS (clientes - Pré-Venda) ---
        # Busca leads ativos (excluindo os arquivados) com os campos mínimos necessários
        response_leads = supabase.table('clientes').select(
            "id, nome_empresa, responsavel, etapa, created_at"
        ).order('created_at', desc=True).neq('etapa', 'Venda Concluída - ARQUIVADO').execute()
        
        leads_raw = response_leads.data
        
        # --- BUSCA 2: CLIENTES PÓS-VENDA (clientes_posvenda) ---
        # Busca clientes de pós-venda com os campos mínimos necessários
        response_posvenda = supabase.table('clientes_posvenda').select(
            "id, nome_empresa, responsavel, etapa, created_at"
        ).order('created_at', desc=True).execute()

        posvenda_raw = response_posvenda.data

        # 2. UNIFICAÇÃO, TIPO E Mapeamento de ID
        
        # Processa Leads (Pré-Venda)
        for lead in leads_raw:
            lead['tipo'] = 'Lead'
            # Mantém o 'id' padrão
            clientes_unificados.append(lead)
            
        # Processa Clientes (Pós-Venda)
        for client in posvenda_raw:
            client['tipo'] = 'Pós-Venda'
            # Renomeia o ID para 'posvenda_id' para evitar conflito no template
            client['posvenda_id'] = client['id'] 
            del client['id'] # Remove o 'id' original para evitar erros
            clientes_unificados.append(client)
        
        # 2.5. ORDENAÇÃO POR DATA DE CRIAÇÃO (Mais recente primeiro)
        # Essencial para garantir que os 'recentes_leads' sejam os mais atuais
        clientes_unificados.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
    except Exception as e:
        error_msg = f"Erro ao buscar dados do dashboard: {e}"
        clientes_unificados = [] 

    # --- INICIALIZAÇÃO E CÁLCULOS ---
    dashboard_data = {
        'total_leads': len(clientes_unificados),
        'contagem_etapas': Counter(),
        'contagem_responsaveis': [],
        'recentes_leads': [],
    }
    
    if clientes_unificados:
        # 3. CONTAGEM DOS STAGES (ETAPAS)
        
        # Agrega TODAS as etapas (Vendas e Pós-Venda) em um único Counter
        etapas_dos_clientes = [c.get('etapa') for c in clientes_unificados if c.get('etapa')]
        dashboard_data['contagem_etapas'] = Counter(etapas_dos_clientes)
        
        # Agrega por Responsável
        responsaveis_dos_clientes_id = [c.get('responsavel') for c in clientes_unificados if c.get('responsavel')]
        contagem_id = Counter(responsaveis_dos_clientes_id).most_common(5)
        contagem_nome = []
        for responsavel_id, contagem in contagem_id:
            nome = employee_map.get(responsavel_id, f"ID {responsavel_id} Desconhecido")
            contagem_nome.append((nome, contagem))
            
        dashboard_data['contagem_responsaveis'] = contagem_nome
        
        # 4. Formatação Final dos Leads Recentes (Top 5 da lista já ordenada)
        recentes_formatados = []
        for lead in clientes_unificados[:5]: 
            responsavel_id = lead.get('responsavel')
            nome = employee_map.get(responsavel_id, 'N/A')
            lead['responsavel_nome'] = nome
            recentes_formatados.append(lead)
            
        dashboard_data['recentes_leads'] = recentes_formatados

    # 5. RENDERIZAÇÃO
    return render_template(
        "negocios.html", 
        base_template_name=get_layout_template(),
        error=error_msg,
        data=dashboard_data,
        # Unifica as configurações de etapas (Pré e Pós-Venda) em um único dicionário para o Jinja
        stages_config={
            **{s['id']: s for s in STAGES_CONFIG}, 
            **{s['id']: s for s in STAGES_CONFIG_POS_TRANSACTION}
        } 
    )
    """Renderiza a página Central de Negócios (Dashboard)."""
    supabase = get_supabase()
    clientes_unificados = []
    error_msg = None
    
    # 1. BUSCAR MAPA DE FUNCIONÁRIOS
    employee_map = get_employees_map(supabase)

    try:
        # --- BUSCA 1: LEADS (clientes) ---
        # response_leads = supabase.table('clientes').select(
        #     "id, etapa, responsavel, nome_empresa, created_at"
        # ).order('created_at', desc=True).neq('etapa', 'Venda Concluída - ARQUIVADO').execute()

        response_leads = supabase.table('clientes').select(
            "id, nome_empresa, nome_contato, email, telefone, responsavel, etapa, created_at, areas(nome)"
        ).order('nome_empresa', desc=False).neq('etapa', 'Venda Concluída - ARQUIVADO').execute()
        
        
        leads_raw = response_leads.data
        
        # --- BUSCA 2: CLIENTES PÓS-VENDA (clientes_posvenda) ---
        response_posvenda = supabase.table('clientes_posvenda').select(
            "id, nome_empresa, nome_contato, email, telefone, responsavel, etapa, created_at, areas(nome)"
        ).order('nome_empresa', desc=False).execute()

        posvenda_raw = response_posvenda.data

        # 2. UNIFICAÇÃO, TIPO E Mapeamento de ID
        
        # Processa Leads (Pré-Venda)
        for lead in leads_raw:
            lead['tipo'] = 'Lead'
            # Já tem o 'id' padrão
            clientes_unificados.append(lead)
            
        # Processa Clientes (Pós-Venda)
        for client in posvenda_raw:
            client['tipo'] = 'Pós-Venda'
            # Renomeia o ID para 'posvenda_id' para evitar conflito no template,
            # e mantém o 'id' original APENAS para contagem, mas isso é mais seguro.
            client['posvenda_id'] = client['id'] # Salva o ID real de pós-venda
            del client['id'] # Remove o 'id' para evitar o erro original no template.
            clientes_unificados.append(client)
        
    except Exception as e:
        error_msg = f"Erro ao buscar dados do dashboard: {e}"
        # Se houver erro, garante que a lista esteja vazia para não travar o loop
        clientes_unificados = [] 

    dashboard_data = {
        'total_leads': 0,
        'contagem_etapas': {},
        'contagem_responsaveis': [],
        # Ordenamos por data (Recentes) após unificação (a busca já fez o order by)
        'recentes_leads': clientes_unificados[:5] 
    }
    
    if clientes_unificados:
        # 3. CONTAGENS E AGRUPAMENTOS
        
        dashboard_data['total_leads'] = len(clientes_unificados)
        
        # Agrega por Etapa (incluindo Pós-Venda)
        etapas_dos_clientes = [c.get('etapa') for c in clientes_unificados if c.get('etapa')]
        dashboard_data['contagem_etapas'] = Counter(etapas_dos_clientes)
        
        # Agrega por Responsável
        responsaveis_dos_clientes_id = [c.get('responsavel') for c in clientes_unificados if c.get('responsavel')]
        
        contagem_id = Counter(responsaveis_dos_clientes_id).most_common(5)
        contagem_nome = []
        for responsavel_id, contagem in contagem_id:
            nome = employee_map.get(responsavel_id, f"ID {responsavel_id} Desconhecido")
            contagem_nome.append((nome, contagem))
            
        dashboard_data['contagem_responsaveis'] = contagem_nome
        
        # 4. Formatação Final dos Leads Recentes
        recentes_formatados = []
        for lead in dashboard_data['recentes_leads']:
            responsavel_id = lead.get('responsavel')
            nome = employee_map.get(responsavel_id, 'N/A')
            lead['responsavel_nome'] = nome
            recentes_formatados.append(lead)
        
        dashboard_data['recentes_leads'] = recentes_formatados


    return render_template(
        "negocios.html", 
        base_template_name=get_layout_template(),
        error=error_msg,
        data=dashboard_data,
        stages_config={**{s['id']: s for s in STAGES_CONFIG}, **{s['id']: s for s in STAGES_CONFIG_POS_TRANSACTION}} 
    )
# ----------------------------------------------------------------------------------------------------------------------------------------------------- #


# --- Rotas de Controle ---

@main_bp.route('/set-layout/<layout_name>')
def set_layout(layout_name):
    """ Salva a preferência de layout do usuário na sessão. """
    if layout_name in ['topbar', 'sidebar']:
        session['layout'] = layout_name
    return redirect(request.referrer or url_for('main.home'))

# --- Rotas de API ---
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