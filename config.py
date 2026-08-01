import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
MONGO_DB = os.getenv('MONGO_DB', 'riomobianalytics')

NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'password')

GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', '')

GTFS_DIR = os.getenv('GTFS_DIR', './data/gtfs/')
RECLAMACOES_1746_FILE = os.getenv('RECLAMACOES_FILE', './data/1746/chamados_v2_com_stops_filtrado.csv')
BAIRROS_LOOKUP_FILE = os.getenv('BAIRROS_FILE', './data/gtfs/Limite_de_Bairros.csv')

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
# Ver MIGRACAO_DATASET.md para justificativa por linha.
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
