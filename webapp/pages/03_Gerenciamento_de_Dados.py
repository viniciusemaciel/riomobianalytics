import subprocess
import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).parent.parent.parent))

from webapp.utils.footer_console import render_query_console
from webapp.utils.theme import (
    apply_theme, render_page_header, render_empty_state, section_title,
    PAGE_ICON,
)

st.set_page_config(page_title="Gerenciamento de Dados · RioMobiAnalytics",
                   page_icon=PAGE_ICON, layout="wide")

apply_theme()

render_page_header(
    "Gerenciamento de dados",
    "Upload de arquivos GTFS/CSV e execução do pipeline ETL passo a passo",
    icon="↑",
)

tab1, tab2, tab3 = st.tabs(["Carregar dados", "Executar pipeline ETL", "Status do sistema"])

with tab1:
    section_title("Arquivos de dados")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Dados GTFS")
        st.caption("Rede de trânsito (paradas, rotas, viagens) em formato GTFS zip.")
        gtfs_file = st.file_uploader(
            "Arquivo zip GTFS",
            type=["zip"],
            help="Ex.: gtfs_rio-de-janeiro.zip",
        )
        if gtfs_file is not None:
            if st.button("Carregar arquivo GTFS", type="primary"):
                try:
                    save_path = Path("data/gtfs") / gtfs_file.name
                    save_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(save_path, "wb") as f:
                        f.write(gtfs_file.getbuffer())
                    st.success(f"Arquivo GTFS carregado em {save_path}")
                except Exception as e:
                    st.error(f"Erro ao carregar arquivo GTFS: {e}")

    with col2:
        st.markdown("#### Reclamações 1746")
        st.caption("CSV oficial de chamados vinculados a paradas.")
        complaint_file = st.file_uploader(
            "Arquivo CSV",
            type=["csv"],
            help="Ex.: chamados_v2_com_stops_filtrado.csv",
        )
        if complaint_file is not None:
            if st.button("Carregar arquivo de reclamações", type="primary"):
                try:
                    save_path = Path("data/1746") / complaint_file.name
                    save_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(save_path, "wb") as f:
                        f.write(complaint_file.getbuffer())
                    st.success(f"Arquivo carregado em {save_path}")
                except Exception as e:
                    st.error(f"Erro ao carregar arquivo: {e}")

with tab2:
    section_title("Controle do pipeline")

    st.warning("Executar scripts ETL **modifica** os bancos. Certifique-se de ter backups.")

    steps = [
        ("01_setup_databases.py", "Configurar bancos", "Inicializar esquemas MongoDB e Neo4j"),
        ("02_load_gtfs_to_neo4j.py", "Carregar GTFS", "Importar rede de trânsito no Neo4j"),
        ("03_load_1746_to_mongodb.py", "Carregar reclamações", "Importar reclamações do 1746 no MongoDB"),
        ("04_sync_1746_to_neo4j.py", "Sincronizar reclamações", "Vincular reclamações às paradas no Neo4j"),
        ("05_calculate_metrics.py", "Calcular métricas", "Pontuações de risco e métricas de rota"),
        ("06_run_analyses.py", "Executar análises", "Algoritmos de análise de grafos"),
    ]

    for script, title, description in steps:
        with st.expander(f"**{title}** · {script}"):
            st.caption(description)
            col1, col2 = st.columns([2, 1])
            with col1:
                st.code(f"python scripts/{script}", language="bash")
            with col2:
                if st.button(f"Executar {title}", key=script,
                             use_container_width=True):
                    with st.spinner(f"Executando {script}..."):
                        try:
                            result = subprocess.run(
                                [sys.executable, f"scripts/{script}"],
                                capture_output=True, text=True, timeout=600,
                            )
                            if result.returncode == 0:
                                st.success(f"{title} concluído")
                                with st.expander("Ver saída"):
                                    st.code(result.stdout)
                            else:
                                st.error(f"{title} falhou")
                                with st.expander("Ver erro"):
                                    st.code(result.stderr)
                        except subprocess.TimeoutExpired:
                            st.error(f"{title} expirou após 10 minutos")
                        except Exception as e:
                            st.error(f"Erro ao executar {title}: {e}")

    st.divider()
    section_title("Executar pipeline completo")
    st.caption("Todas as etapas em sequência.")

    if st.button("Executar pipeline completo", type="primary",
                 use_container_width=True):
        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, (script, title, _) in enumerate(steps):
            status_text.text(f"Etapa {i+1}/{len(steps)} · {title}")
            progress_bar.progress(i / len(steps))
            try:
                result = subprocess.run(
                    [sys.executable, f"scripts/{script}"],
                    capture_output=True, text=True, timeout=600,
                )
                if result.returncode == 0:
                    st.success(f"✓ {title} concluído")
                else:
                    st.error(f"✗ {title} falhou")
                    st.code(result.stderr)
                    break
            except Exception as e:
                st.error(f"Erro em {title}: {e}")
                break

        progress_bar.progress(1.0)
        status_text.text("Pipeline concluído.")

with tab3:
    section_title("Status do sistema")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### MongoDB")
        try:
            from webapp.utils.db_connections import get_mongo_db
            db = get_mongo_db()
            count = db.reclamacoes_1746_raw.count_documents({})
            synced = db.reclamacoes_1746_raw.count_documents({"synced_to_neo4j": True})
            st.success("MongoDB conectado")
            st.metric("Total de reclamações", f"{count:,}".replace(",", "."))
            st.metric("Sincronizado com Neo4j", f"{synced:,}".replace(",", "."))
            if count > 0:
                sync_percentage = (synced / count) * 100
                st.progress(sync_percentage / 100)
                st.caption(f"{sync_percentage:.1f}% sincronizado")
        except Exception as e:
            st.error(f"Falha na conexão com MongoDB: {e}")

    with col2:
        st.markdown("#### Neo4j")
        try:
            from webapp.utils.db_connections import query_neo4j
            result = query_neo4j("MATCH (n) RETURN count(n) as total")
            total_nodes = result[0]["total"] if result else 0
            result = query_neo4j("MATCH ()-[r]->() RETURN count(r) as total")
            total_relationships = result[0]["total"] if result else 0
            st.success("Neo4j conectado")
            st.metric("Total de nós", f"{total_nodes:,}".replace(",", "."))
            st.metric("Total de relacionamentos",
                      f"{total_relationships:,}".replace(",", "."))
        except Exception as e:
            st.error(f"Falha na conexão com Neo4j: {e}")

    st.divider()
    section_title("Diretório de dados")

    data_path = Path("data")
    if data_path.exists():
        gtfs_path = data_path / "gtfs"
        complaints_path = data_path / "1746"

        col3, col4 = st.columns(2)
        with col3:
            st.markdown("**Arquivos GTFS**")
            if gtfs_path.exists():
                files = list(gtfs_path.glob("*"))
                if files:
                    for f in files:
                        size_mb = f.stat().st_size / (1024 * 1024)
                        st.text(f"· {f.name} ({size_mb:.1f} MB)")
                else:
                    render_empty_state("Sem arquivos GTFS",
                                       "Faça upload na aba Carregar dados.")
            else:
                render_empty_state("Diretório não encontrado",
                                   "data/gtfs ainda não existe.")

        with col4:
            st.markdown("**Arquivos de reclamações**")
            if complaints_path.exists():
                files = list(complaints_path.glob("*.csv"))
                if files:
                    for f in files:
                        size_mb = f.stat().st_size / (1024 * 1024)
                        st.text(f"· {f.name} ({size_mb:.1f} MB)")
                else:
                    render_empty_state("Sem arquivos CSV",
                                       "Faça upload na aba Carregar dados.")
            else:
                render_empty_state("Diretório não encontrado",
                                   "data/1746 ainda não existe.")
    else:
        render_empty_state("Diretório data/ não encontrado",
                           "Rode o pipeline ETL a partir do repositório.")

st.info("Atualize a página após executar as etapas ETL para ver estatísticas frescas.")

render_query_console()
