import contextlib
import contextvars

from pymongo import MongoClient
from neo4j import GraphDatabase, Query, READ_ACCESS
import streamlit as st
import config
import time
from .query_logger import QueryLogger

# Quando ligado, toda consulta Neo4j da thread atual abre sessão em modo de leitura:
# o próprio banco recusa escrita. O assistente (webapp/rag) roda sempre assim.
_somente_leitura = contextvars.ContextVar("neo4j_somente_leitura", default=False)


@contextlib.contextmanager
def somente_leitura():
    token = _somente_leitura.set(True)
    try:
        yield
    finally:
        _somente_leitura.reset(token)


@st.cache_resource
def get_mongo_client():
    return MongoClient(config.MONGO_URI)

@st.cache_resource
def get_neo4j_driver():
    return GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
    )

def get_mongo_db():
    client = get_mongo_client()
    return client[config.MONGO_DB]

def query_neo4j(cypher_query, parameters=None, timeout=None):
    """`timeout` (segundos), quando dado, vira timeout da transação: o Neo4j cancela a consulta."""
    driver = get_neo4j_driver()
    start_time = time.time()

    try:
        sessao = driver.session(default_access_mode=READ_ACCESS) if _somente_leitura.get() else driver.session()
        with sessao as session:
            consulta = Query(cypher_query, timeout=timeout) if timeout else cypher_query
            result = session.run(consulta, parameters or {})
            records = [record.data() for record in result]

        duration_ms = (time.time() - start_time) * 1000
        QueryLogger.log_neo4j(cypher_query, parameters, duration_ms)

        return records
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        QueryLogger.log_neo4j(cypher_query, parameters, duration_ms)
        raise
