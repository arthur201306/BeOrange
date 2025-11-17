import os
from supabase import create_client
from dotenv import load_dotenv

# Carregar as variáveis do .env
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

# Variáveis de ambiente
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

# Verificar se as variáveis estão corretas
if not url or not key:
    print("Erro: SUPABASE_URL ou SUPABASE_KEY não encontradas nas variáveis de ambiente.")
    exit(1)

# Criação do cliente Supabase
supabase = create_client(url, key)

# Definir as colunas a serem selecionadas (passar como string com colunas separadas por vírgula)
KANBAN_COLUMNS = "id, nome_empresa, nome_contato, etapa, responsavel, created_at, areas"

# Testar a consulta
def test_supabase_query():
    try:
        print("Consultando dados da tabela 'clientes'...")

        # Realiza a consulta passando as colunas como uma string separada por vírgula
        response = supabase.table('clientes').select(KANBAN_COLUMNS).order('created_at', desc=True).execute()

        # Adicionando um log para ver o conteúdo da resposta
        print("Resposta do Supabase:", response)

        # Checar se existem dados
        if not response.data:
            print("Nenhum dado encontrado na tabela 'clientes'.")
        else:
            print(f"Consulta bem-sucedida! Encontrados {len(response.data)} registros.")
            # Exibir os primeiros 3 registros para verificação
            for lead in response.data[:3]:  # Apenas os 3 primeiros registros
                print(lead)

    except Exception as e:
        print(f"Erro ao consultar os dados: {e}")

# Chama a função de teste
test_supabase_query()
