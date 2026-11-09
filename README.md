# RioMobiAnalytics

**Graph-based risk analysis of Rio de Janeiro's bus network.** RioMobiAnalytics links every bus stop to nearby citizen complaints from the city's 1746 service line and to a machine-learning estimate of shooting risk, producing a single, explainable risk score per stop. Everything is explorable in an interactive Streamlit app backed by Neo4j and MongoDB.

> Postgraduate project in Data Science.

## What it does

- **Models the transit network as a graph.** Stops, routes and trips from the city's GTFS feed live in Neo4j; consecutive stops on a trip are connected, so network structure (e.g. PageRank) becomes a feature.
- **Connects complaints to stops.** Citizen complaints from the 1746 line (lighting, public safety, road conditions, etc.) are stored in MongoDB and linked to the nearest stop within 100 m.
- **Predicts shooting risk.** An XGBoost classifier trained on [Fogo Cruzado](https://fogocruzado.org.br/) occurrences estimates the probability of a shooting within 500 m of each stop, using stop geography, network position and rolling complaint counts.
- **Combines both signals.** Each stop gets a reactive score (open complaints, weighted by category) and a predictive score (model probability), merged into one normalized 0–100 score and ranked in quartiles.

```
risk_total = (0.6 × complaint_risk + 1.4 × shooting_probability) / 2
```

## The app

| Page | What you can do |
|---|---|
| **Home** | System KPIs, risk distribution and navigation |
| **Interactive map** | Stops colored by risk level and complaint locations by category |
| **Network graph** | Transit topology with nodes colored by total risk |
| **Explore details** | Look up a stop or complaint protocol and see its links |
| **Methodology** | End-to-end explanation of how the score is computed |
| **Predictive model** | Inspect features, performance and run what-if scenarios on the XGBoost model |

## Architecture

```
GTFS + 1746 + Fogo Cruzado  ──►  scripts/ (one-off load)  ──►  Neo4j AuraDB  (graph + scores)
                                                          └─►  MongoDB Atlas (raw complaints)
                                                                     ▲
                                  artifacts/ (trained model)         │ live queries
                                              └────────────►  Streamlit app (webapp/)
```

The app only **reads** from the databases; all loading and scoring happens offline in `scripts/`.

## Data

| Source | Use |
|---|---|
| GTFS Rio de Janeiro (`stops`, `routes`, `trips`, `stop_times`) | Stops, routes and the connection graph |
| Central 1746 complaints (`data/1746`) | Reactive risk and model features |
| Fogo Cruzado shootings (`data/fogocruzado`) | Target variable for the predictive model |
| Neighborhood boundaries (`Limite_de_Bairros.csv`) | Maps neighborhood ids to names |

## Model

XGBoost binary classifier at stop × month granularity (16 features: location, number of routes, PageRank and 3/6/12-month complaint counts by category). Chronological split: train 2021-01 to 2023-12, validation 2024, test 2025. Reported validation AUC is about 0.71. See the Methodology and Predictive model pages for feature importance and details.

## Repository structure

```
├── webapp/                  Streamlit app (entry point: webapp/Home.py)
│   ├── pages/               Map, graph, details, methodology, model
│   ├── utils/               DB connections, cached queries, theme, query console
│   └── assets/              Logo, favicon, CSS
├── scripts/                 Database loading and scoring
│   ├── 01_setup_databases.py       reset databases, create indexes/constraints
│   ├── 02_load_gtfs_to_neo4j.py    stops, routes, trips, connections
│   ├── 03_load_1746_to_mongodb.py  complaints → MongoDB
│   ├── 04_sync_1746_to_neo4j.py    complaints → graph (AFFECTS)
│   ├── 05_calculate_metrics.py     complaint-based risk per stop
│   ├── 06_pagerank.py              PageRank (networkx, same as training)
│   ├── 07_predict_risk.py          model prediction + total risk
│   └── run_all.sh                  runs 01 → 07
├── notebooks/               Data preparation, EDA, features, model training
├── artifacts/               Trained model, scaler, metadata, validation set
├── data/                    GTFS, 1746 and Fogo Cruzado input files
├── docs/research_paper.md   Project paper
├── config.py                Credentials, paths and pipeline parameters
└── requirements.txt
```

## Getting started

**Requirements:** Python 3.10+, a [Neo4j AuraDB](https://neo4j.com/cloud/aura/) instance and a [MongoDB Atlas](https://www.mongodb.com/atlas) cluster (both have free tiers).

```bash
git clone git@github.com:viniciusemaciel/riomobianalytics.git
cd riomobianalytics
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # fill in your Neo4j and MongoDB credentials
```

### Load the databases

Run once, or whenever you want to rebuild from scratch. Step 01 **deletes** existing data in both databases.

```bash
FORCE_RESET=true ./scripts/run_all.sh
```

Each step can also be run on its own, e.g. `python3 scripts/06_pagerank.py`.

### Run the app

```bash
streamlit run webapp/Home.py
```

## Configuration

`config.py` reads credentials from environment variables / `.env` first and falls back to Streamlit secrets.

| Variable | Description |
|---|---|
| `NEO4J_URI` | Bolt URI, e.g. `neo4j+s://<id>.databases.neo4j.io` |
| `NEO4J_USERNAME` | Neo4j user (`NEO4J_USER` also accepted) |
| `NEO4J_PASSWORD` | Neo4j password |
| `MONGODB_URI` | Atlas URI, with or without credentials |
| `MONGODB_USERNAME` / `MONGODB_PASSWORD` | Injected into the URI when it has none |
| `MONGO_DB` | Database name (default `riomobianalytics`) |

## Deploy on Streamlit Community Cloud

1. Create an app at [share.streamlit.io](https://share.streamlit.io) pointing to this repository, branch `main`, main file `webapp/Home.py`.
2. In **Settings → Secrets**, paste the keys from `.streamlit/secrets.toml.example` (values in quotes, TOML format).
3. In MongoDB Atlas, allow `0.0.0.0/0` under **Network Access** (Streamlit Cloud has no fixed IP).

Notes for demos: AuraDB Free pauses after a few idle days (resume it in the console), and Streamlit Cloud apps sleep after about 12 hours without traffic, so open the app a few minutes beforehand.

## Retraining the model

Run the notebooks in order (from the repo root or `notebooks/`):

1. `01_filtragem_gtfs_1746.ipynb` — filters the raw GTFS and 1746 files (run originally on Databricks).
2. `02_eda_fogo_cruzado.ipynb` — exploratory analysis of shooting data.
3. `03_feature_engineering.ipynb` — builds `data/model_dataset.parquet`, including PageRank.
4. `04_treino_modelo.ipynb` — trains and compares models, saves the winner to `artifacts/`.

## Notes and limitations

- Neo4j AuraDB Free does not include the Graph Data Science plugin, so PageRank is computed in Python with the same parameters used for training.
- Complaint-to-stop links use proximity (≤ 100 m), not causality; the score ranks relative exposure, it is not a safety guarantee.
- Fogo Cruzado data is a point-in-time export; scores should be refreshed when the data is.

## Tech stack

Python · Streamlit · Neo4j · MongoDB · XGBoost · scikit-learn · NetworkX · Plotly · Folium · pandas
