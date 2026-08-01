import streamlit as st
from .query_logger import QueryLogger


def render_query_console():
    """Console de queries no rodapé — colapsada por padrão para não poluir a página."""

    logs = QueryLogger.get_logs()
    stats = QueryLogger.get_stats()

    st.markdown("<div class='rm-console-footer'></div>", unsafe_allow_html=True)

    summary = (
        f"Console de queries · {stats['total_queries']} total · "
        f"Neo4j {stats['neo4j_queries']} · MongoDB {stats['mongo_queries']} · "
        f"{stats['total_duration_ms']:.0f} ms"
    )

    with st.expander(summary, expanded=False):
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("Limpar histórico", key="clear_console", use_container_width=True):
                QueryLogger.clear_logs()
                st.rerun()
        with col2:
            if st.button("Atualizar", key="refresh_console", use_container_width=True):
                st.rerun()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total", stats["total_queries"])
        c2.metric("Neo4j", stats["neo4j_queries"])
        c3.metric("MongoDB", stats["mongo_queries"])
        c4.metric("Tempo (ms)", f"{stats['total_duration_ms']:.0f}")

        if not logs:
            st.caption("Nenhuma query executada ainda.")
            return

        tab_all, tab_neo, tab_mongo = st.tabs(["Todas", "Neo4j", "MongoDB"])
        with tab_all:
            _display_logs(logs)
        with tab_neo:
            _display_logs([l for l in logs if l.get("database") == "Neo4j"])
        with tab_mongo:
            _display_logs([l for l in logs if l.get("database") == "MongoDB"])


def _display_logs(logs):
    if not logs:
        st.caption("Nada registrado nesta aba.")
        return

    for log in reversed(logs):
        timestamp = log.get("timestamp", "N/A")
        database = log.get("database", "N/A")
        duration = log.get("duration_ms", 0)
        status = log.get("status", "?")

        if database == "Neo4j":
            query_preview = (log.get("query", "")[:60] + "...").replace("\n", " ")
            title = f"{status} · {timestamp} · Neo4j · {query_preview}"
        else:
            operation = log.get("operation", "N/A")
            query_preview = str(log.get("query", ""))[:60]
            title = f"{status} · {timestamp} · Mongo {operation} · {query_preview}"

        with st.expander(title, expanded=False):
            c1, c2 = st.columns(2)
            c1.write(f"**Database**: {database}")
            c1.write(f"**Tempo**: {duration:.2f} ms")
            c2.write(f"**Timestamp**: {timestamp}")
            c2.write(f"**Status**: {status}")

            if database == "Neo4j":
                st.markdown("**Query Cypher**")
                st.code(log.get("query", ""), language="cypher")
                if log.get("parameters"):
                    st.markdown("**Parâmetros**")
                    st.json(log.get("parameters", {}))
            else:
                st.markdown("**Operação**")
                st.write(log.get("operation", "N/A"))
                st.markdown("**Query**")
                st.code(str(log.get("query", "")), language="json")


def render_minimal_console():
    """Versão inline minimalista (mantida por compatibilidade)."""
    stats = QueryLogger.get_stats()
    cols = st.columns([2, 1, 1, 1, 1])
    cols[0].caption("Query stats")
    cols[1].caption(f"Total: {stats['total_queries']}")
    cols[2].caption(f"Neo4j: {stats['neo4j_queries']}")
    cols[3].caption(f"MongoDB: {stats['mongo_queries']}")
    cols[4].caption(f"Tempo: {stats['total_duration_ms']:.0f} ms")
