"""
Configuração central do RioMobiAnalytics.

Ordem de leitura das credenciais:
  1. variáveis de ambiente / arquivo .env (desenvolvimento local e scripts)
  2. st.secrets (Streamlit Community Cloud)
Caminhos são absolutos a partir da raiz do repo, então app e scripts
funcionam independentemente do diretório de execução.
"""
import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _secret(*keys, default=None):
    """Primeiro valor encontrado entre as chaves, no ambiente ou em st.secrets."""
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    try:
        import streamlit as st
        for key in keys:
            if key in st.secrets:
                return str(st.secrets[key])
    except Exception:
        pass
    return default


def _mongo_uri():
    uri = _secret("MONGO_URI", "MONGODB_URI", default="mongodb://localhost:27017/")
    user = _secret("MONGODB_USERNAME")
    pwd = _secret("MONGODB_PASSWORD")
    # Atlas: se a URI veio sem credenciais, injeta usuário/senha (com escape)
    if user and pwd and "@" not in uri.split("://", 1)[-1].split("/", 1)[0]:
        scheme, rest = uri.split("://", 1)
        uri = f"{scheme}://{quote_plus(user)}:{quote_plus(pwd)}@{rest}"
    return uri


# ---------------- Bancos ----------------
MONGO_URI = _mongo_uri()
MONGO_DB = _secret("MONGO_DB", default="riomobianalytics")

NEO4J_URI = _secret("NEO4J_URI", default="bolt://localhost:7687")
NEO4J_USER = _secret("NEO4J_USER", "NEO4J_USERNAME", default="neo4j")
NEO4J_PASSWORD = _secret("NEO4J_PASSWORD", default="password")

# ---------------- Assistente (RAG) ----------------
ANTHROPIC_API_KEY = _secret("ANTHROPIC_API_KEY")
RAG_MODEL = _secret("RAG_MODEL", default="claude-haiku-5-5")
RAG_MAX_PERGUNTAS_SESSAO = int(_secret("RAG_MAX_PERGUNTAS_SESSAO", default="30"))
RAG_MAX_RODADAS = 6        # rodadas de ferramenta por pergunta
RAG_MAX_HISTORICO = 10     # mensagens do histórico enviadas ao modelo
RAG_PRECO_ENTRADA_MTOK = float(_secret("RAG_PRECO_ENTRADA_MTOK", default="0.10"))  # US$ por 1M tokens (estimativa)
RAG_PRECO_SAIDA_MTOK = float(_secret("RAG_PRECO_SAIDA_MTOK", default="0.50"))

# ---------------- Caminhos ----------------
DATA_DIR = BASE_DIR / "data"
ARTIFACTS_DIR = BASE_DIR / "artifacts"

GTFS_DIR = os.getenv("GTFS_DIR", str(DATA_DIR / "gtfs"))
RECLAMACOES_1746_FILE = os.getenv(
    "RECLAMACOES_FILE", str(DATA_DIR / "1746" / "chamados_v2_com_stops_filtrado.csv")
)
BAIRROS_LOOKUP_FILE = os.getenv("BAIRROS_FILE", str(DATA_DIR / "gtfs" / "Limite_de_Bairros.csv"))

# ---------------- Parâmetros do pipeline ----------------
BATCH_SIZE = 1000
MAX_DISTANCE_AFFECTS_METERS = 100

CATEGORIA_PESOS = {
    'Segurança Pública': 1.5,
    'Iluminação Pública': 0.6,
    'Conservação de Vias': 0.5,
    'Limpeza Urbana': 0.4,
    'Trânsito e Transporte': 0.8,
    'Outros': 0.3
}

CHAMADOS_V2_COLUMN_MAPPING = {
    'id_chamado': 'protocolo',
    'data_inicio': 'data_abertura',
    'latitude': 'latitude',
    'longitude': 'longitude',
}

CHAMADOS_V2_DEFAULTS = {
    'status': 'Aberto',
    'criticidade': 'Baixa',
    'descricao': '',
    'bairro': ''
}

# Curadoria de tipos: apenas chamados relacionados à segurança/experiência
# em paradas de ônibus são carregados. Chaves são valores da coluna `tipo`
# no CSV chamados_v2_com_stops_filtrado; valores são a categoria canônica
# usada por CATEGORIA_PESOS. Tipos ausentes deste mapa são descartados.
TIPO_TO_SERVICO = {
    'Iluminação Pública': 'Iluminação Pública',
    'Reformulação de iluminação pública': 'Iluminação Pública',
    'Manutenção de iluminação pública': 'Iluminação Pública',
    'Guarda Municipal / Fiscalização de trânsito': 'Segurança Pública',
    'Ordem pública': 'Segurança Pública',
    'Ouvidoria SEOP': 'Segurança Pública',
    'Patrulhamento público': 'Segurança Pública',
    'Conservação de vias': 'Conservação de Vias',
    'Vias públicas': 'Conservação de Vias',
    'Ouvidoria SECONSERMA': 'Conservação de Vias',
    'Mobiliário Urbano': 'Conservação de Vias',
    'Ônibus': 'Trânsito e Transporte',
    'Regulamentações Viárias': 'Trânsito e Transporte',
    'Diversos - Comlurb': 'Limpeza Urbana',
}
