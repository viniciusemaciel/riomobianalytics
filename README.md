# RioMobiAnalytics

Análise de risco em paradas de ônibus do Rio de Janeiro, combinando a rede de transporte (GTFS), reclamações da Central 1746 e um modelo preditivo de tiroteios (XGBoost treinado com dados do Fogo Cruzado).

O app Streamlit lê, ao vivo, um grafo no **Neo4j** (paradas, rotas, reclamações) e os dados brutos no **MongoDB**.

## Estrutura

```
├── webapp/                 App Streamlit (entrada: webapp/Home.py)
│   ├── pages/              Mapa, Grafo, Explorar, Metodologia, Modelo preditivo
│   ├── utils/              Conexões, consultas cacheadas, tema, console de queries
│   └── assets/             Logo, favicon e CSS
├── scripts/                Carga dos bancos (rodada uma vez, fora do app)
│   ├── 01_setup_databases.py      limpa bancos e cria índices
│   ├── 02_load_gtfs_to_neo4j.py   paradas, rotas, viagens, conexões
│   ├── 03_load_1746_to_mongodb.py reclamações 1746 → MongoDB
│   ├── 04_sync_1746_to_neo4j.py   reclamações → grafo (AFFECTS)
│   ├── 05_calculate_metrics.py    risco reativo por parada
│   ├── 06_pagerank.py             PageRank (networkx, igual ao treino)
│   ├── 07_predict_risk.py         risco preditivo + risco total
│   └── run_all.sh                 executa 01 → 07
├── notebooks/              Preparação dos dados, features e treino do modelo
├── artifacts/              Modelo treinado (xgb_model, scaler, metadata, validação)
├── data/                   GTFS (4 arquivos + bairros), 1746 e Fogo Cruzado
├── docs/research_paper.md  Artigo do projeto
├── config.py               Credenciais, caminhos e parâmetros
└── requirements.txt
```

## Rodar localmente

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # preencha as credenciais do Aura e do Atlas
streamlit run webapp/Home.py
```

## Carregar os bancos

Necessário só uma vez (ou para recarregar do zero). Usa as credenciais do `.env`.

```bash
FORCE_RESET=true ./scripts/run_all.sh
```

O passo 01 **apaga** os dados existentes nos dois bancos. Cada script também roda isolado: `python3 scripts/06_pagerank.py`.

## Deploy (Streamlit Community Cloud)

1. Em share.streamlit.io, crie o app apontando para este repositório, branch `main`, arquivo `webapp/Home.py`.
2. Em *Settings → Secrets*, cole as chaves de `.streamlit/secrets.toml.example` preenchidas.
3. No MongoDB Atlas, libere `0.0.0.0/0` em *Network Access* (o Cloud não tem IP fixo).

O `config.py` lê as credenciais do ambiente/`.env` e, se não encontrar, de `st.secrets`.

## Observações

- O Neo4j AuraDB Free pausa após alguns dias sem uso; retome a instância no console antes de apresentar.
- O AuraDB Free não tem o plugin GDS; por isso o PageRank é calculado em Python (`06_pagerank.py`), com os mesmos parâmetros usados no treino.
- Para retreinar o modelo, gere `data/model_dataset.parquet` com `notebooks/03_feature_engineering.ipynb` e rode `notebooks/04_treino_modelo.ipynb`; os artefatos são salvos em `artifacts/`.
