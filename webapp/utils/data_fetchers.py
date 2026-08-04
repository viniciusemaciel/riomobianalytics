import pandas as pd
from .db_connections import get_mongo_db, query_neo4j
import streamlit as st
from .query_logger import QueryLogger
import time


@st.cache_data(ttl=300)
def get_stops_with_risk():
    query = """
    MATCH (s:Stop)
    RETURN s.id as id, s.name as name, s.lat as lat, s.lon as lon,
           COALESCE(s.risk_score_atual, 0)        AS risk_score_atual,
           COALESCE(s.risk_score_tiroteio, 0)     AS risk_score_tiroteio,
           COALESCE(s.risk_score_total, 0)        AS risk_score_total,
           COALESCE(s.risk_score_normalized, 0)   AS risk_score_normalized,
           s.risk_level                           AS risk_level,
           COALESCE(s.total_reclamacoes, 0)       AS total_complaints
    ORDER BY s.risk_score_normalized DESC
    """
    data = query_neo4j(query)
    df = pd.DataFrame(data)
    if "risk_level" in df.columns:
        df["risk_level"] = df["risk_level"].replace({
            "Medio-Alto": "Médio-Alto",
            "Medio-Baixo": "Médio-Baixo",
        })
    return df


@st.cache_data(ttl=300)
def get_routes_with_metrics():
    query = """
    MATCH (r:Route)
    RETURN r.id as id, r.short_name as name, r.long_name as full_name,
           r.avg_risk_score as avg_risk, r.total_stops as total_stops,
           r.high_risk_stops as high_risk_stops
    ORDER BY r.avg_risk_score DESC
    """
    data = query_neo4j(query)
    return pd.DataFrame(data)


@st.cache_data(ttl=300)
def get_complaints_summary():
    db = get_mongo_db()
    start_time = time.time()

    pipeline = [
        {"$group": {
            "_id": "$servico",
            "count": {"$sum": 1},
            "avg_peso": {"$avg": "$peso"}
        }},
        {"$sort": {"count": -1}}
    ]

    results = list(db.reclamacoes_1746_raw.aggregate(pipeline))

    duration_ms = (time.time() - start_time) * 1000
    QueryLogger.log_mongodb("aggregate", {"collection": "reclamacoes_1746_raw"}, None, duration_ms)

    return pd.DataFrame(results).rename(columns={"_id": "category"})


@st.cache_data(ttl=300)
def get_network_graph_data(limit: int = 500):
    """Retorna as primeiras `limit` conexões CONNECTS_TO do banco.

    É uma amostra "arbitrária" da rede (ordem definida pelo Neo4j), útil
    para dar uma visão geral da topologia. Para focar em uma região
    específica, use `get_network_around_stop`.
    """
    query = f"""
    MATCH (s1:Stop)-[c:CONNECTS_TO]->(s2:Stop)
    RETURN s1.id as source, s2.id as target, s1.name as source_name,
           s2.name as target_name, c.distance_meters as distance,
           c.risk_adjusted_cost as cost,
           COALESCE(s1.risk_score_total, 0) as source_risk,
           COALESCE(s2.risk_score_total, 0) as target_risk
    LIMIT {int(limit)}
    """
    data = query_neo4j(query)
    return pd.DataFrame(data)


@st.cache_data(ttl=300)
def get_network_around_stop(stop_id: str, max_edges: int = 500):
    """Retorna arestas CONNECTS_TO acessíveis a partir de `stop_id` via BFS.

    Faz uma travessia em largura no Neo4j até coletar até `max_edges` arestas
    únicas. Útil para gerar um subgrafo conectado, centrado em uma parada
    específica, em vez da amostragem "aleatória" de `get_network_graph_data`.
    """
    query = """
    MATCH path = (start:Stop {id: $stop_id})-[:CONNECTS_TO*1..6]-(other:Stop)
    WITH relationships(path) AS rels
    UNWIND rels AS r
    WITH DISTINCT r
    LIMIT $max_edges
    WITH startNode(r) AS s1, endNode(r) AS s2, r
    RETURN s1.id AS source, s2.id AS target,
           s1.name AS source_name, s2.name AS target_name,
           r.distance_meters AS distance,
           r.risk_adjusted_cost AS cost,
           COALESCE(s1.risk_score_total, 0) AS source_risk,
           COALESCE(s2.risk_score_total, 0) AS target_risk
    """
    data = query_neo4j(query, {"stop_id": stop_id, "max_edges": int(max_edges)})
    return pd.DataFrame(data)


@st.cache_data(ttl=300)
def get_system_stats():
    query = """
    MATCH (s:Stop)
    WHERE s.risk_score_total IS NOT NULL
      AND s.risk_score_normalized IS NOT NULL
    WITH count(s) as total_stops,
         avg(s.risk_score_normalized) as avg_risk_normalized,
         count(CASE WHEN s.risk_level = 'Alto' THEN 1 END) as high_risk_stops,
         count(CASE WHEN s.risk_score_tiroteio >= 0.5 THEN 1 END) as high_tiroteio_stops

    MATCH (r:Route)
    WITH total_stops, avg_risk_normalized, high_risk_stops, high_tiroteio_stops,
         count(r) as total_routes

    MATCH (rec:Reclamacao)
    WITH total_stops, avg_risk_normalized, high_risk_stops, high_tiroteio_stops,
         total_routes,
         count(rec) as total_complaints,
         count(CASE WHEN rec.status = 'Aberto' THEN 1 END) as open_complaints

    RETURN total_stops, total_routes, total_complaints, open_complaints,
           avg_risk_normalized as avg_risk, high_risk_stops, high_tiroteio_stops
    """
    data = query_neo4j(query)
    return data[0] if data else {}


@st.cache_data(ttl=300)
def get_top_critical_stops(limit=10):
    query = f"""
    MATCH (s:Stop)
    WHERE s.risk_score_total > 0
    RETURN s.name as name,
           COALESCE(s.risk_score_total, 0) as risk,
           COALESCE(s.risk_score_atual, 0) as risk_atual,
           COALESCE(s.risk_score_tiroteio, 0) as risk_tiroteio,
           s.lat as lat, s.lon as lon,
           s.risk_level as risk_level
    ORDER BY s.risk_score_total DESC
    LIMIT {limit}
    """
    data = query_neo4j(query)
    df = pd.DataFrame(data)
    if "risk_level" in df.columns:
        df["risk_level"] = df["risk_level"].replace({
            "Medio-Alto": "Médio-Alto",
            "Medio-Baixo": "Médio-Baixo",
        })
    return df


@st.cache_data(ttl=300)
def get_complaints_by_location():
    db = get_mongo_db()
    start_time = time.time()

    complaints = list(db.reclamacoes_1746_raw.find(
        {},
        {"protocolo": 1, "lat": 1, "lon": 1, "servico": 1, "bairro": 1, "_id": 0}
    ).limit(1000))

    duration_ms = (time.time() - start_time) * 1000
    QueryLogger.log_mongodb("find", {"collection": "reclamacoes_1746_raw"}, None, duration_ms)

    return pd.DataFrame(complaints)


@st.cache_data(ttl=300)
def get_stop_details(stop_id):
    """Get detailed information about a specific stop, including risk decomposition."""
    query = """
    MATCH (s:Stop {id: $stop_id})
    OPTIONAL MATCH (r:Route)-[:SERVES]->(s)
    OPTIONAL MATCH (rec:Reclamacao)-[:AFFECTS]->(s)
    WHERE rec.status IN ['Aberto', 'Em Atendimento']
    RETURN
      s.id as id,
      s.name as name,
      s.lat as lat,
      s.lon as lon,
      COALESCE(s.risk_score_total, 0) as risk_score_total,
      COALESCE(s.risk_score_atual, 0) as risk_score_atual,
      COALESCE(s.risk_score_tiroteio, 0) as risk_score_tiroteio,
      COALESCE(s.risk_score_normalized, 0) as risk_score_normalized,
      COALESCE(s.risk_level, 'Sem risco') as risk_level,
      COALESCE(s.total_reclamacoes, 0) as total_complaints,
      COALESCE(s.reclamacoes_abertas, 0) as open_complaints,
      s.wheelchair_accessible as wheelchair_accessible,
      collect(DISTINCT r.short_name) as routes,
      count(DISTINCT rec) as active_complaints
    """
    data = query_neo4j(query, {"stop_id": stop_id})
    result = data[0] if data else None
    if result and result.get("risk_level") in ("Medio-Alto", "Medio-Baixo"):
        result["risk_level"] = result["risk_level"].replace("Medio", "Médio")
    return result


@st.cache_data(ttl=300)
def get_stop_complaints(stop_id):
    """Get all complaints affecting a specific stop"""
    query = """
    MATCH (rec:Reclamacao)-[:AFFECTS]->(s:Stop {id: $stop_id})
    RETURN
      rec.protocolo as protocolo,
      toString(rec.data_abertura) as data_abertura,
      rec.servico as servico,
      rec.status as status,
      rec.criticidade as criticidade,
      rec.peso as peso,
      rec.bairro as bairro,
      rec.descricao as descricao
    ORDER BY rec.data_abertura DESC
    """
    data = query_neo4j(query, {"stop_id": stop_id})
    return pd.DataFrame(data)


@st.cache_data(ttl=300)
def get_complaint_details(protocolo):
    """Get detailed information about a specific complaint"""
    query = """
    MATCH (rec:Reclamacao {protocolo: $protocolo})
    OPTIONAL MATCH (rec)-[:AFFECTS]->(s:Stop)
    OPTIONAL MATCH (rec)-[:HAS_TYPE]->(c:Categoria)
    RETURN
      rec.id as id,
      rec.protocolo as protocolo,
      toString(rec.data_abertura) as data_abertura,
      rec.servico as servico,
      rec.status as status,
      rec.criticidade as criticidade,
      rec.peso as peso,
      rec.lat as lat,
      rec.lon as lon,
      rec.bairro as bairro,
      rec.descricao as descricao,
      collect(DISTINCT s.name) as affected_stops,
      count(DISTINCT s) as stop_count,
      c.peso_base as category_weight
    """
    data = query_neo4j(query, {"protocolo": protocolo})
    return data[0] if data else None


@st.cache_data(ttl=300)
def get_nearby_complaints(lat, lon, radius_meters=500):
    """Get complaints near a specific location"""
    db = get_mongo_db()
    start_time = time.time()

    complaints = list(db.reclamacoes_1746_raw.find(
        {
            "localizacao": {
                "$near": {
                    "$geometry": {
                        "type": "Point",
                        "coordinates": [lon, lat]
                    },
                    "$maxDistance": radius_meters
                }
            }
        },
        {
            "protocolo": 1,
            "data_abertura": 1,
            "servico": 1,
            "bairro": 1,
            "lat": 1,
            "lon": 1,
            "_id": 0
        }
    ).limit(50))

    duration_ms = (time.time() - start_time) * 1000
    QueryLogger.log_mongodb("geoNear", {"collection": "reclamacoes_1746_raw"}, None, duration_ms)

    return pd.DataFrame(complaints)


@st.cache_data(ttl=300)
def get_stop_routes(stop_id):
    """Get all routes serving a specific stop"""
    query = """
    MATCH (r:Route)-[:SERVES]->(s:Stop {id: $stop_id})
    RETURN
      r.id as id,
      r.short_name as short_name,
      r.long_name as long_name,
      r.type as type,
      r.avg_risk_score as avg_risk
    ORDER BY r.short_name
    """
    data = query_neo4j(query, {"stop_id": stop_id})
    return pd.DataFrame(data)


@st.cache_data(ttl=300)
def get_connected_stops(stop_id, hops=2):
    """Get stops connected to a specific stop"""
    query = f"""
    MATCH (start:Stop {{id: $stop_id}})-[:CONNECTS_TO*1..{hops}]-(connected:Stop)
    RETURN
      connected.id as id,
      connected.name as name,
      COALESCE(connected.risk_score_total, 0) as risk_score,
      connected.risk_level as risk_level,
      COALESCE(connected.total_reclamacoes, 0) as total_complaints
    ORDER BY connected.risk_score_total DESC
    LIMIT 50
    """
    data = query_neo4j(query, {"stop_id": stop_id})
    df = pd.DataFrame(data)
    if "risk_level" in df.columns:
        df["risk_level"] = df["risk_level"].replace({
            "Medio-Alto": "Médio-Alto",
            "Medio-Baixo": "Médio-Baixo",
        })
    return df


@st.cache_data(ttl=300)
def get_stop_features_for_model(stop_id: str):
    """Retorna todas as features usadas pelo modelo XGBoost para uma parada.

    Útil para o playground do modelo (página 06) — mostra os valores
    exatos de cada feature e permite simulação what-if.
    """
    from datetime import date
    from dateutil.relativedelta import relativedelta
    import math

    hoje = date.today()
    mes_corrente_start = date(hoje.year, hoje.month, 1)
    date_3m = mes_corrente_start - relativedelta(months=3)
    date_6m = mes_corrente_start - relativedelta(months=6)
    date_12m = mes_corrente_start - relativedelta(months=12)

    query = """
        MATCH (s:Stop {id: $stop_id})
        OPTIONAL MATCH (rec:Reclamacao)-[:AFFECTS]->(s)
        WHERE date(rec.data_abertura) >= date($date_12m)
          AND date(rec.data_abertura) <  date($mes_corrente)

        WITH s,
             count(rec) AS total_12m,
             count(CASE WHEN date(rec.data_abertura) >= date($date_6m) THEN rec END) AS total_6m,
             count(CASE WHEN date(rec.data_abertura) >= date($date_3m) THEN rec END) AS total_3m,

             count(CASE WHEN rec.servico = 'Segurança Pública' THEN rec END) AS seg_12m,
             count(CASE WHEN rec.servico = 'Segurança Pública'
                        AND date(rec.data_abertura) >= date($date_6m) THEN rec END) AS seg_6m,
             count(CASE WHEN rec.servico = 'Segurança Pública'
                        AND date(rec.data_abertura) >= date($date_3m) THEN rec END) AS seg_3m,

             count(CASE WHEN rec.servico = 'Iluminação Pública' THEN rec END) AS ilum_12m,
             count(CASE WHEN rec.servico = 'Iluminação Pública'
                        AND date(rec.data_abertura) >= date($date_6m) THEN rec END) AS ilum_6m,
             count(CASE WHEN rec.servico = 'Iluminação Pública'
                        AND date(rec.data_abertura) >= date($date_3m) THEN rec END) AS ilum_3m

        OPTIONAL MATCH (r:Route)-[:SERVES]->(s)
        RETURN s.id          AS stop_id,
               s.name        AS name,
               s.lat         AS lat,
               s.lon         AS lon,
               count(DISTINCT r)               AS num_rotas_servindo,
               COALESCE(s.pagerank, 0.0)       AS pagerank,
               COALESCE(s.risk_score_atual, 0) AS risk_score_atual,
               COALESCE(s.risk_score_tiroteio, 0) AS risk_score_tiroteio,
               COALESCE(s.risk_score_total, 0) AS risk_score_total,
               COALESCE(s.risk_score_normalized, 0) AS risk_score_normalized,
               s.risk_level                    AS risk_level,
               total_3m, total_6m, total_12m,
               seg_3m, seg_6m, seg_12m,
               ilum_3m, ilum_6m, ilum_12m
    """
    params = {
        "stop_id": stop_id,
        "mes_corrente": str(mes_corrente_start),
        "date_3m": str(date_3m),
        "date_6m": str(date_6m),
        "date_12m": str(date_12m),
    }
    data = query_neo4j(query, params)
    if not data:
        return None
    result = data[0]
    if result.get("risk_level") == "Medio-Baixo":
        result["risk_level"] = "Médio-Baixo"
    elif result.get("risk_level") == "Medio-Alto":
        result["risk_level"] = "Médio-Alto"

    # Adiciona features temporais do mês corrente
    result["ano"] = hoje.year
    result["mes"] = hoje.month
    result["mes_sin"] = math.sin(2 * math.pi * hoje.month / 12)
    result["mes_cos"] = math.cos(2 * math.pi * hoje.month / 12)
    return result
