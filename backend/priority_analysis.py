import os
import psycopg2
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# --- Configurações do Banco de Dados PostGIS ---
DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_PORT = os.getenv('DB_PORT')

# --- Parâmetros de Priorização ---
# Distância em metros para considerar vazamentos "próximos"
PROXIMITY_RADIUS_METER = 100
# Período (em dias) para considerar vazamentos "recentes" reparados
RECENT_REPAIRED_DAYS = 30


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


def calculate_priority_score(conn):
    """
    Calcula e atualiza o score de prioridade para vazamentos no banco de dados.
    A lógica inclui:
    1. Proximidade com outros vazamentos ATIVOS.
    2. Proximidade com vazamentos RECENTEMENTE REPARADOS (indica recorrência).
    3. Múltiplas denúncias para o mesmo ponto (se houvesse um mecanismo para agrupá-las).
    """
    # Consulta para identificar vazamentos a serem processados (novos ou ativos)
    # Por simplicidade, processamos todos os 'reportado' ou 'em_inspecao'
    select_vazamentos_sql = """
                            SELECT id_kobo, \
                                   localizacao, \
                                   status, \
                                   data_submissao
                            FROM vazamentos_denuncias
                            WHERE status IN ('reportado', 'em_inspecao')
                            ORDER BY data_submissao ASC; \
                            """

    # SQL para atualizar o score de prioridade
    update_score_sql = """
                       UPDATE vazamentos_denuncias
                       SET prioridade_score = %s,
                           updated_at       = NOW()
                       WHERE id_kobo = %s; \
                       """

    try:
        with conn.cursor() as cur:
            cur.execute(select_vazamentos_sql)
            vazamentos_a_processar = cur.fetchall()

            for vazamento_id, geom, status, data_submissao in vazamentos_a_processar:
                current_score = 0

                # 1. Vazamentos Ativos Próximos
                # Busca vazamentos ATIVOS (status='reportado' ou 'em_inspecao')
                # dentro de um raio definido, excluindo o próprio vazamento.
                query_active_nearby = """
                                      SELECT COUNT(id_kobo)
                                      FROM vazamentos_denuncias
                                      WHERE id_kobo != %s \
                                        AND
                                          status IN ('reportado' \
                                          , 'em_inspecao') \
                                        AND
                                          ST_DWithin(%s::geography \
                                          , localizacao::geography \
                                          , %s); \
                                      """
                cur.execute(query_active_nearby, (vazamento_id, geom.to_wkt(), PROXIMITY_RADIUS_METER))
                num_active_nearby = cur.fetchone()[0]
                current_score += num_active_nearby * 3  # Cada vazamento ativo próximo aumenta 3 pontos

                # 2. Vazamentos Recém-Reparados Próximos (Indica recorrência)
                # Busca vazamentos com status 'reparado' nos últimos RECENT_REPAIRED_DAYS
                # dentro do raio de proximidade.
                recent_repaired_limit = datetime.now() - timedelta(days=RECENT_REPAIRED_DAYS)
                query_repaired_nearby = """
                                        SELECT COUNT(id_kobo)
                                        FROM vazamentos_denuncias
                                        WHERE id_kobo != %s \
                                          AND
                                            status = 'reparado' \
                                          AND
                                            data_submissao >= %s \
                                          AND
                                            ST_DWithin(%s::geography \
                                            , localizacao::geography \
                                            , %s); \
                                        """
                cur.execute(query_repaired_nearby,
                            (vazamento_id, recent_repaired_limit, geom.to_wkt(), PROXIMITY_RADIUS_METER))
                num_repaired_nearby = cur.fetchone()[0]
                current_score += num_repaired_nearby * 5  # Recorrência é mais grave, 5 pontos

                # 3. Denúncias Múltiplas para o Mesmo Ponto (Simplificado)
                # Se tivéssemos um agrupamento de denúncias por local muito similar
                # (além da proximidade), poderíamos dar um peso maior aqui.
                # Por agora, a proximidade já ajuda a inferir isso.

                # 4. Impacto do Vazamento (se disponível do formulário)
                # Se o formulário do Kobo trouxesse 'intensidade_vazamento' como 'severe', adicionar mais pontos.
                # Para isso, teríamos que ter o 'intensidade_vazamento' já na query inicial ou fazer um JOIN.
                # Exemplo (se 'intensidade_vazamento' estivesse no 'vazamentos_a_processar'):
                # if vazamento_data.get('intensidade_vazamento') == 'severe':
                #    current_score += 10

                # Atualiza o score no banco de dados
                cur.execute(update_score_sql, (current_score, vazamento_id))

            conn.commit()
            print(f"Scores de prioridade calculados e atualizados para {len(vazamentos_a_processar)} vazamentos.")

    except psycopg2.Error as e:
        print(f"Erro ao calcular prioridade: {e}")


def run_priority_analysis():
    """
    Função principal para executar a análise de prioridade.
    """
    conn = connect_db()
    if not conn:
        return

    try:
        calculate_priority_score(conn)
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    print("Iniciando a análise de prioridade...")
    run_priority_analysis()
    print("Análise de prioridade concluída.")