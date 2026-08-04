"""
Modelo preditivo — playground interativo.

Permite inspecionar as features de qualquer parada, simular cenários
what-if (ajustando contagens de chamados manualmente) e ver a predição
do XGBoost em tempo real.
"""

import math
import sys
from pathlib import Path

import joblib
import json
import numpy as np
import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).parent.parent.parent))

from webapp.utils.data_fetchers import (
    get_stops_with_risk,
    get_stop_features_for_model,
)
from webapp.utils.footer_console import render_query_console
from webapp.utils.theme import (
    apply_theme, render_page_header, render_risk_badge,
    render_empty_state, section_title, BRAND, PAGE_ICON,
)

st.set_page_config(page_title="Modelo Preditivo · RioMobiAnalytics",
                   page_icon=PAGE_ICON, layout="wide")

apply_theme()

render_page_header(
    "Modelo preditivo",
    "Playground interativo do XGBoost — inspecione features, simule cenários e entenda as predições",
    icon="⟐",
)

# ---------------------------------------------------------------------------
# Cache dos artefatos do modelo
# ---------------------------------------------------------------------------
@st.cache_resource
def load_model_artifacts():
    artifacts_dir = Path(__file__).resolve().parent.parent.parent / "artifacts"
    model = joblib.load(artifacts_dir / "xgb_model.joblib")
    scaler = joblib.load(artifacts_dir / "scaler.joblib")
    with open(artifacts_dir / "metadata.json") as f:
        meta = json.load(f)
    return model, scaler, meta


def predict_from_features(features_dict: dict, model, scaler, meta) -> float:
    """Roda o modelo com um dicionário de features e retorna a probabilidade."""
    feature_order = meta["features"]
    row = np.array([[features_dict.get(f, 0) for f in feature_order]])

    # log1p nas colunas de contagem (mesmo índice do treino)
    count_cols = [f for f in feature_order if f.startswith("num_reclamacoes_")]
    for col in count_cols:
        idx = feature_order.index(col)
        row[0, idx] = np.log1p(row[0, idx])

    row_scaled = scaler.transform(row)
    return float(model.predict_proba(row_scaled)[0, 1])


# ---------------------------------------------------------------------------
# Carrega modelo e stops
# ---------------------------------------------------------------------------
model, scaler, meta = load_model_artifacts()
stops_df = get_stops_with_risk()

if stops_df.empty:
    render_empty_state("Sem dados", "Execute o pipeline ETL primeiro.")
    st.stop()

# ---------------------------------------------------------------------------
# TABS
# ---------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs([
    "Consultar parada real",
    "Simulador what-if",
    "Info do modelo",
])

# =========================================================================
# TAB 1 — consulta parada real
# =========================================================================
with tab1:
    section_title("Predição de uma parada real",
                  "selecione uma parada e veja os valores que o modelo usou")

    stop_names = sorted(stops_df[stops_df["name"].notna()]["name"].unique())
    selected_name = st.selectbox("Parada", stop_names, key="tab1_stop")
    selected_stop = stops_df[stops_df["name"] == selected_name].iloc[0]
    stop_id = selected_stop["id"]

    features = get_stop_features_for_model(stop_id)
    if not features:
        st.error("Parada não encontrada no grafo.")
        st.stop()

    # --- Card de predição atual ---
    st.divider()
    st.markdown("#### Resultado da predição")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Risco Total", f"{features['risk_score_normalized']:.1f} / 100")
    with c2:
        st.metric("Risco por Chamados", f"{features['risk_score_atual'] * 100:.0f} / 100")
    with c3:
        st.metric("Risco de Tiroteio (ML)", f"{features['risk_score_tiroteio'] * 100:.0f}%")
    with c4:
        st.markdown("**Nível**")
        st.markdown(
            render_risk_badge(features.get("risk_level")),
            unsafe_allow_html=True,
        )

    # --- Tabela de features ---
    st.divider()
    st.markdown("#### Features usadas pelo modelo")

    feature_order = meta["features"]
    count_cols = [f for f in feature_order if f.startswith("num_reclamacoes_")]
    raw_values = {f: features.get(f, 0) for f in feature_order}
    transformed = raw_values.copy()
    for c in count_cols:
        transformed[c] = np.log1p(raw_values[c])

    rows = []
    for f in feature_order:
        rows.append({
            "Feature": f,
            "Valor bruto": round(raw_values[f], 4) if f not in count_cols else int(raw_values[f]),
            "Após transformação": round(transformed[f], 4),
        })

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
        height=560,
    )

    st.caption(
        "Transformações: log1p nas 9 colunas de contagem; depois StandardScaler "
        "em todas as 16 features antes da predição."
    )

# =========================================================================
# TAB 2 — Simulador what-if
# =========================================================================
with tab2:
    section_title("Simulador what-if",
                  "ajuste as features manualmente e veja como a predição muda")

    st.markdown(
        "Escolha uma parada como ponto de partida e altere as contagens "
        "de chamados para simular cenários hipotéticos."
    )

    sim_name = st.selectbox(
        "Parada de referência",
        stop_names,
        key="tab2_stop",
    )
    sim_stop = stops_df[stops_df["name"] == sim_name].iloc[0]
    sim_features = get_stop_features_for_model(sim_stop["id"])
    if not sim_features:
        st.error("Parada não encontrada.")
        st.stop()

    # Sliders para cada grupo de features
    st.divider()

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**Chamados — janela 3 meses**")
        t3 = st.slider("Total (3m)", 0, 500, int(sim_features.get("total_3m", 0)), step=1)
        s3 = st.slider("Segurança Pública (3m)", 0, 200, int(sim_features.get("seg_3m", 0)), step=1)
        i3 = st.slider("Iluminação Pública (3m)", 0, 200, int(sim_features.get("ilum_3m", 0)), step=1)

        st.markdown("**Chamados — janela 6 meses**")
        t6 = st.slider("Total (6m)", 0, 500, int(sim_features.get("total_6m", 0)), step=1)
        s6 = st.slider("Segurança Pública (6m)", 0, 200, int(sim_features.get("seg_6m", 0)), step=1)
        i6 = st.slider("Iluminação Pública (6m)", 0, 200, int(sim_features.get("ilum_6m", 0)), step=1)

    with col_b:
        st.markdown("**Chamados — janela 12 meses**")
        t12 = st.slider("Total (12m)", 0, 1000, int(sim_features.get("total_12m", 0)), step=1)
        s12 = st.slider("Segurança Pública (12m)", 0, 400, int(sim_features.get("seg_12m", 0)), step=1)
        i12 = st.slider("Iluminação Pública (12m)", 0, 400, int(sim_features.get("ilum_12m", 0)), step=1)

        # Features estáticas — readonly, mas mostradas
        st.markdown("**Features estáticas (fixas da parada)**")
        st.caption(f"lat: {sim_features['lat']:.6f}")
        st.caption(f"lon: {sim_features['lon']:.6f}")
        st.caption(f"Rotas servindo: {sim_features['num_rotas_servindo']}")
        st.caption(f"Pagerank: {sim_features['pagerank']:.6f}")
        st.caption(f"Ano: {sim_features['ano']}  |  Mês: {sim_features['mes']}")

    # --- Monta features e prediz ---
    sim_dict = {
        "lat": sim_features["lat"],
        "lon": sim_features["lon"],
        "num_rotas_servindo": sim_features["num_rotas_servindo"],
        "pagerank": sim_features["pagerank"],
        "num_reclamacoes_3m": t3,
        "num_reclamacoes_6m": t6,
        "num_reclamacoes_12m": t12,
        "num_reclamacoes_seguranca_3m": s3,
        "num_reclamacoes_seguranca_6m": s6,
        "num_reclamacoes_seguranca_12m": s12,
        "num_reclamacoes_iluminacao_3m": i3,
        "num_reclamacoes_iluminacao_6m": i6,
        "num_reclamacoes_iluminacao_12m": i12,
        "ano": sim_features["ano"],
        "mes_sin": sim_features["mes_sin"],
        "mes_cos": sim_features["mes_cos"],
    }

    prob_sim = predict_from_features(sim_dict, model, scaler, meta)

    risco_atual = sim_features["risk_score_atual"]
    risco_total = (0.6 * risco_atual + 1.4 * prob_sim) / 2.0

    # Nível simulado (quartis do range)
    # Usamos os thresholds da última predição em batch como referência
    total_min = stops_df["risk_score_total"].min()
    total_max = stops_df["risk_score_total"].max()
    normalized_sim = (risco_total - total_min) / (total_max - total_min) * 100 if total_max != total_min else 50
    step = (100.0 - 0.0) / 4.0  # range sempre 0-100 após min-max
    if normalized_sim >= 75:
        sim_level = "Alto"
    elif normalized_sim >= 50:
        sim_level = "Médio-Alto"
    elif normalized_sim >= 25:
        sim_level = "Médio-Baixo"
    else:
        sim_level = "Baixo"

    st.divider()
    st.markdown("#### Predição do cenário simulado")

    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        st.metric("Prob. de tiroteio (XGBoost)", f"{prob_sim * 100:.1f}%",
                  delta=f"{(prob_sim - sim_features['risk_score_tiroteio']) * 100:+.1f} pp")
    with sc2:
        st.metric("Risco Total simulado", f"{normalized_sim:.1f} / 100")
    with sc3:
        st.markdown("**Nível simulado**")
        st.markdown(render_risk_badge(sim_level), unsafe_allow_html=True)

    st.caption(
        f"Fórmula: (0.6 × {risco_atual*100:.0f} + 1.4 × {prob_sim*100:.0f}%) / 2 = {normalized_sim:.1f}"
    )

# =========================================================================
# TAB 3 — Info do modelo
# =========================================================================
with tab3:
    section_title("Informações do modelo em produção")

    st.markdown("#### Artefatos carregados")
    info_df = pd.DataFrame([
        {"Artefato": "Modelo",          "Arquivo": "xgb_model.joblib",  "Tamanho": "787 KB"},
        {"Artefato": "Scaler",          "Arquivo": "scaler.joblib",     "Tamanho": "1.5 KB"},
        {"Artefato": "Metadados",       "Arquivo": "metadata.json",     "Tamanho": "1.7 KB"},
        {"Artefato": "Predições val.",  "Arquivo": "val_predictions.parquet", "Tamanho": "622 KB"},
    ])
    st.dataframe(info_df, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("#### Hiperparâmetros")
    params = meta.get("best_params", {})
    relevant = {
        "learning_rate": "Taxa de aprendizado",
        "max_depth": "Profundidade máxima",
        "n_estimators": "Nº de árvores",
        "subsample": "Subamostragem",
        "scale_pos_weight": "Peso da classe positiva",
        "eval_metric": "Métrica de avaliação",
    }
    hp_rows = []
    for k, label in relevant.items():
        if k in params:
            hp_rows.append({"Parâmetro": label, "Valor": str(params[k])})
    st.dataframe(pd.DataFrame(hp_rows), use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("#### Períodos de treino/validação/teste")
    st.markdown(f"- Treino: {meta['train_period']}")
    st.markdown(f"- Validação: {meta['val_period']}")
    st.markdown(f"- Teste: {meta['test_period']}")

    st.divider()
    st.markdown("#### Como consumir o modelo via código")
    st.code(
        """import joblib, json, numpy as np

# Carrega artefatos
model = joblib.load("artifacts/xgb_model.joblib")
scaler = joblib.load("artifacts/scaler.joblib")
with open("artifacts/metadata.json") as f:
    meta = json.load(f)

# Monta vetor de features na ordem exata
features = np.array([[
    -22.9129,  # lat
    -43.2103,  # lon
    12,        # num_rotas_servindo
    0.00034,   # pagerank
    5, 12, 30, # num_reclamacoes_3m, 6m, 12m
    1, 3, 8,   # num_reclamacoes_seguranca_3m, 6m, 12m
    2, 4, 10,  # num_reclamacoes_iluminacao_3m, 6m, 12m
    2026,      # ano
    0.5,       # mes_sin
    -0.866,    # mes_cos
]])

# Transformações
count_idx = [4,5,6,7,8,9,10,11,12]  # índices das colunas de contagem
features[0, count_idx] = np.log1p(features[0, count_idx])
features_scaled = scaler.transform(features)

# Predição
prob_tiroteio = model.predict_proba(features_scaled)[0, 1]
print(f"Probabilidade de tiroteio: {prob_tiroteio:.2%}")
""",
        language="python",
    )

render_query_console()
