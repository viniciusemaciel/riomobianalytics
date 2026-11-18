import streamlit as st
from datetime import datetime

class QueryLogger:
    """Logger para capturar e armazenar queries executadas"""

    @staticmethod
    def initialize():
        """Inicializa o logger no session state"""
        if "query_log" not in st.session_state:
            st.session_state.query_log = []

    @staticmethod
    def log_neo4j(query, parameters=None, duration_ms=0):
        """Registra uma query Neo4j"""
        QueryLogger.initialize()

        log_entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "database": "Neo4j",
            "query": query,
            "parameters": parameters,
            "duration_ms": duration_ms,
            "status": "✓"
        }

        st.session_state.query_log.append(log_entry)

        # Manter apenas os últimos 50 registros
        if len(st.session_state.query_log) > 50:
            st.session_state.query_log = st.session_state.query_log[-50:]

    @staticmethod
    def log_mongodb(operation, filter_query=None, update_query=None, duration_ms=0):
        """Registra uma operação MongoDB"""
        QueryLogger.initialize()

        query_str = f"Collection: {filter_query.get('collection', 'unknown')}" if isinstance(filter_query, dict) else str(filter_query)

        log_entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "database": "MongoDB",
            "operation": operation,
            "query": query_str,
            "duration_ms": duration_ms,
            "status": "✓"
        }

        st.session_state.query_log.append(log_entry)

        # Manter apenas os últimos 50 registros
        if len(st.session_state.query_log) > 50:
            st.session_state.query_log = st.session_state.query_log[-50:]

    @staticmethod
    def get_logs():
        """Retorna todos os logs"""
        QueryLogger.initialize()
        return st.session_state.query_log

    @staticmethod
    def clear_logs():
        """Limpa todos os logs"""
        st.session_state.query_log = []

    @staticmethod
    def get_stats():
        """Retorna estatísticas dos logs"""
        logs = QueryLogger.get_logs()

        neo4j_count = len([l for l in logs if l["database"] == "Neo4j"])
        mongo_count = len([l for l in logs if l["database"] == "MongoDB"])
        total_duration = sum(l.get("duration_ms", 0) for l in logs)

        return {
            "total_queries": len(logs),
            "neo4j_queries": neo4j_count,
            "mongo_queries": mongo_count,
            "total_duration_ms": total_duration
        }
