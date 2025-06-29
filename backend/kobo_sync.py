import os
import requests
import psycopg2
from dotenv import load_dotenv
import json

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# --- Configurações da API do KoboToolbox ---
KOBO_API_URL = os.getenv('KOBO_API_URL')
KOBO_TOKEN = os.getenv('KOBO_TOKEN')
HEADERS = {'Authorization': KOBO_TOKEN, 'Accept': 'application/json'}

# --- Configurações do Banco de Dados PostGIS ---
DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_PORT = os.getenv('DB_PORT')

def get_kobo_data():
    """
    Busca os dados mais recentes do formulário no KoboToolbox.
    Retorna uma lista de dicionários com as submissões.
    """
    try:
        response = requests.get(KOBO_API_URL, headers=HEADERS)
        response.raise_for_status() # Levanta um erro para status HTTP de erro (4xx ou 5xx)
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar dados do KoboToolbox: {e}")
        return None

def connect_db():
    """
    Estabelece conexão com o banco de dados PostGIS.
    Retorna o objeto de conexão.
    """
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        return conn
    except psycopg2.Error as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        return None

def create_table_if_not_exists(conn):
    """
    Cria a tabela 'vazamentos_denuncias' no PostGIS se ela não existir.
    """
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS vazamentos_denuncias (
        id_kobo VARCHAR(255) PRIMARY KEY,
        data_submissao TIMESTAMP WITH TIME ZONE,
        localizacao GEOMETRY(Point, 4326),
        tipo_vazamento VARCHAR(50),
        intensidade_vazamento VARCHAR(50),
        origem_vazamento VARCHAR(50),
        descricao_detalhes TEXT,
        foto_url TEXT,
        prioridade_score INTEGER DEFAULT 0,
        status VARCHAR(50) DEFAULT 'reportado',
        osm_tags JSONB, -- Para armazenar as tags do OSM como JSON
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_vazamentos_localizacao ON vazamentos_denuncias USING GIST(localizacao);
    """
    try:
        with conn.cursor() as cur:
            cur.execute(create_table_sql)
        conn.commit()
        print("Tabela 'vazamentos_denuncias' verificada/criada com sucesso.")
    except psycopg2.Error as e:
        print(f"Erro ao criar tabela: {e}")

def insert_or_update_vazamento(conn, vazamento_data):
    """
    Insere uma nova denúncia de vazamento ou atualiza uma existente no PostGIS.
    """
    sql_insert = """
    INSERT INTO vazamentos_denuncias (
        id_kobo, data_submissao, localizacao, tipo_vazamento, intensidade_vazamento,
        origem_vazamento, descricao_detalhes, foto_url, osm_tags
    ) VALUES (
        %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s, %s, %s, %s
    ) ON CONFLICT (id_kobo) DO UPDATE SET
        data_submissao = EXCLUDED.data_submissao,
        localizacao = EXCLUDED.localizacao,
        tipo_vazamento = EXCLUDED.tipo_vazamento,
        intensidade_vazamento = EXCLUDED.intensidade_vazamento,
        origem_vazamento = EXCLUDED.origem_vazamento,
        descricao_detalhes = EXCLUDED.descricao_detalhes,
        foto_url = EXCLUDED.foto_url,
        osm_tags = EXCLUDED.osm_tags,
        updated_at = NOW();
    """
    try:
        with conn.cursor() as cur:
            # Extrair os dados do Kobo e mapear para as colunas do DB
            kobo_id = vazamento_data.get('_id')
            submission_time = vazamento_data.get('_submission_time')
            # Kobo retorna a localização como "lat long alt acc"
            location_str = vazamento_data.get('localizacao_vazamento')
            if location_str:
                lat, lon, _, _ = map(float, location_str.split())
            else:
                lat, lon = None, None

            tipo_vazamento = vazamento_data.get('tipo_vazamento') # 'leak' ou 'pipe_burst'
            intensidade_vazamento = vazamento_data.get('intensidade_vazamento') # 'minor', 'moderate', 'severe'
            origem_vazamento = vazamento_data.get('origem_vazamento') # 'pipe', 'valve', 'hydrant', 'unknown'
            descricao_detalhes = vazamento_data.get('descricao_detalhes')
            foto_filename = vazamento_data.get('foto_vazamento')
            # No Kobo, as fotos ficam em um subdiretório. Montar a URL completa depois.
            # Por enquanto, armazenamos apenas o nome do arquivo, a URL completa pode ser gerada pelo frontend ou backend.
            foto_url = f"{KOBO_API_URL.split('/data/')[0]}/attachments/{foto_filename}" if foto_filename else None

            # Construir o objeto JSON para osm_tags com base no formulário XLSForm
            osm_tags = {}
            if tipo_vazamento:
                osm_tags['waterway'] = tipo_vazamento # Ex: waterway=leak ou waterway=pipe_burst
                if tipo_vazamento == 'pipe_burst':
                    osm_tags['leak'] = 'pipe_burst' # Para ser mais específico, de acordo com o guia OSM

            if intensidade_vazamento:
                osm_tags['leak'] = intensidade_vazamento # Ex: leak=minor, leak=severe
            if origem_vazamento:
                osm_tags['leak:source'] = origem_vazamento # Ex: leak:source=pipe
            if descricao_detalhes:
                osm_tags['description'] = descricao_detalhes
            if foto_url:
                osm_tags['image'] = foto_url # ou 'photo:url'

            cur.execute(sql_insert, (
                kobo_id, submission_time, lon, lat, tipo_vazamento,
                intensidade_vazamento, origem_vazamento, descricao_detalhes,
                foto_url, json.dumps(osm_tags) # Converte o dicionário para JSON string
            ))
        conn.commit()
        print(f"Denúncia Kobo ID {kobo_id} inserida/atualizada com sucesso.")
    except psycopg2.Error as e:
        print(f"Erro ao inserir/atualizar vazamento {kobo_id}: {e}")

def run_sync():
    """
    Função principal para executar a sincronização.
    """
    kobo_data = get_kobo_data()
    if not kobo_data:
        print("Nenhum dado novo do KoboToolbox para processar.")
        return

    conn = connect_db()
    if not conn:
        return

    try:
        create_table_if_not_exists(conn)
        for vazamento in kobo_data:
            # O KoboToolbox retorna todas as submissões a cada chamada da API.
            # Para evitar reprocessamento desnecessário, você pode implementar
            # um controle de 'último ID processado' ou 'última data/hora processada'
            # para buscar apenas as novas submissões.
            # Por simplicidade, este exemplo fará UPSERT (UPDATE OR INSERT).
            insert_or_update_vazamento(conn, vazamento)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    run_sync()