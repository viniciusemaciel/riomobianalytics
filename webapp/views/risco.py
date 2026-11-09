"""Risco — como o modelo de tiroteio se comporta e um simulador para explorar cenários."""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from webapp.utils.data_fetchers import get_stop_features_for_model, get_stops_with_risk
from webapp.utils.insights import FEATURE_LABELS, feature_importance, load_metadata, model_metrics
from webapp.utils.state import get_selected
from webapp.utils.theme import (
    LINE, MUTED, NAVY, ORANGE, TEXT_2, fmt_dec, fmt_int, normalize_level, page_header,
    plotly_layout, risk_badge,
)

ARTIFACTS = Path(__file__).resolve().parent.parent.parent / "artifacts"


@st.cache_resource
def load_model():
    model = joblib.load(ARTIFACTS / "xgb_model.joblib")
    scaler = joblib.load(ARTIFACTS / "scaler.joblib")
    with open(ARTIFACTS / "metadata.json") as f:
        meta = json.load(f)
    return model, scaler, meta


def predict(features: dict, model, scaler, meta) -> float:
    order = meta["features"]
    row = np.array([[features.get(f, 0) for f in order]], dtype=float)
    for i, f in enumerate(order):
        if f.startswith("num_reclamacoes_"):
            row[0, i] = np.log1p(row[0, i])
    return float(model.predict_proba(scaler.transform(row))[0, 1])


meta = load_metadata()
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def periodo(txt: str) -> str:
    try:
        a, b = [p.strip() for p in txt.split(" - ")]
        f = lambda s: f"{MESES[int(s[5:7]) - 1]}/{s[:4]}"
        return f"{f(a)} a {f(b)}"
    except Exception:
        return txt
m = model_metrics()

page_header(
    "Modelo de risco",
    "Índice de risco",
    "O índice de cada parada (0 a 100) combina reclamações da Central 1746 com um modelo XGBoost que estima "
    "tiroteio a até 500 m da parada. Aqui estão as métricas do modelo no período de validação.",
)

# ---------- Períodos ----------
st.markdown(
    "<div class='rm-periods'>"
    f"<div style='flex:3;border-radius:8px 0 0 8px'><b>Treino</b> · {periodo(meta.get('train_period', ''))}</div>"
    f"<div style='flex:1;background:{NAVY};color:#fff'><b>Validação</b> · {periodo(meta.get('val_period', ''))}</div>"
    f"<div style='flex:1;border-radius:0 8px 8px 0'><b>Teste</b> · {periodo(meta.get('test_period', ''))}</div>"
    "</div>",
    unsafe_allow_html=True,
)

if m:
    kpis = [
        (fmt_dec(m["auc"]), "AUC", "Capacidade de ordenar paradas por risco. 0,5 seria sorteio."),
        (f"{m['recall'] * 100:.0f}%", "Recall", "Dos meses com tiroteio, quantos o modelo marcou."),
        (f"{m['precision'] * 100:.0f}%", "Precisão", "Dos meses marcados, quantos tiveram tiroteio."),
        (f"{m['base_rate'] * 100:.0f}%", "Taxa real", "Meses com tiroteio no entorno, entre todos os pares parada e mês."),
    ]
    cols = st.columns(4)
    for col, (v, l, h) in zip(cols, kpis):
        with col:
            with st.container(border=True):
                st.markdown(
                    f"<div class='rm-muted'>{l}</div><div style='font-size:2rem;font-weight:500;letter-spacing:-.03em;"
                    f"margin:2px 0 4px'>{v}</div><div class='rm-muted' style='font-size:.82rem;min-height:2.6em'>{h}</div>",
                    unsafe_allow_html=True,
                )
    st.caption(f"Corte de classificação em {fmt_dec(m['threshold'])}. {fmt_int(m['n'])} pares parada e mês, "
               f"{fmt_int(m['n_stops'])} paradas.")

    # ---------- Gráficos ----------
    g1, g2 = st.columns(2, gap="medium")
    with g1:
        with st.container(border=True):
            dec = pd.DataFrame(m["deciles"])
            top = dec["taxa"].iloc[-1] * 100
            st.markdown(
                f"<div style='font-size:1.1rem;font-weight:500'>O modelo ordena bem as paradas</div>"
                f"<div class='rm-muted' style='margin:4px 0 8px'>Taxa real de tiroteio por decil do score. "
                f"No decil mais alto, {top:.0f}% dos meses tiveram tiroteio. O score serve para comparar paradas, não é probabilidade.</div>",
                unsafe_allow_html=True,
            )
            colors = ["#CCD3DC"] * (len(dec) - 3) + ["#F3A188", "#F3A188", ORANGE]
            fig = go.Figure(go.Bar(
                x=[f"{i + 1}º" for i in range(len(dec))], y=dec["taxa"] * 100, marker_color=colors,
                text=[f"{v * 100:.0f}%" if i == len(dec) - 1 else "" for i, v in enumerate(dec["taxa"])],
                textposition="outside", hovertemplate="Decil %{x}: %{y:.1f}% dos meses<extra></extra>",
            ))
            fig.add_hline(y=m["base_rate"] * 100, line=dict(color=NAVY, dash="dash", width=1),
                          annotation_text=f"taxa média {m['base_rate'] * 100:.0f}%", annotation_position="top left",
                          annotation_font=dict(size=11, color=NAVY))
            plotly_layout(fig, height=320, margin=dict(l=8, r=8, t=16, b=8))
            fig.update_yaxes(ticksuffix="%", gridcolor="#EEF1F4", zeroline=False, tickfont=dict(color=MUTED, size=11))
            fig.update_xaxes(title=dict(text="decil do score (1º = mais baixo)", font=dict(size=11, color=TEXT_2)),
                             tickfont=dict(color=MUTED, size=11))
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    with g2:
        with st.container(border=True):
            imp = feature_importance()[:8]
            loc = sum(v for n, _, v in feature_importance() if n in ("lat", "lon")) * 100
            st.markdown(
                f"<div style='font-size:1.1rem;font-weight:500'>Localização pesa mais que as reclamações</div>"
                f"<div class='rm-muted' style='margin:4px 0 8px'>Ganho de cada variável no modelo. Latitude e longitude somam {loc:.0f}%.</div>",
                unsafe_allow_html=True,
            )
            if imp:
                labels = [l for _, l, _ in imp][::-1]
                vals = [v * 100 for _, _, v in imp][::-1]
                colors = [NAVY if n in ("lat", "lon") else "#B8C2CE" for n, _, _ in imp][::-1]
                fig = go.Figure(go.Bar(x=vals, y=labels, orientation="h", marker_color=colors,
                                       text=[f"{v:.0f}%" for v in vals], textposition="outside",
                                       hovertemplate="%{y}: %{x:.1f}%<extra></extra>"))
                plotly_layout(fig, height=320, margin=dict(l=8, r=30, t=8, b=8))
                fig.update_xaxes(visible=False, range=[0, max(vals) * 1.35])
                fig.update_yaxes(tickfont=dict(size=11.5, color=NAVY), automargin=True)
                st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

# ---------- Explorar ----------
st.markdown("<div class='rm-section'><div class='rm-eyebrow'>Explorar o modelo</div>"
            "<h2>Consultar uma parada e simular cenários</h2></div>", unsafe_allow_html=True)

try:
    stops_df = get_stops_with_risk()
except Exception as e:
    st.error(f"Não foi possível carregar as paradas: {e}")
    st.stop()
stops_df = stops_df[stops_df["name"].notna()].sort_values("name")
ids = stops_df["id"].tolist()
labels = dict(zip(stops_df["id"], stops_df["name"]))
sel = get_selected()
model, scaler, _ = load_model()

tab1, tab2, tab3 = st.tabs(["Consultar parada", "Simulador", "Detalhes técnicos"])

with tab1:
    stop_id = st.selectbox("Parada", ids, index=ids.index(sel) if sel in ids else 0,
                           format_func=lambda i: labels.get(i, i), key="risco_parada")
    feats = get_stop_features_for_model(stop_id)
    if not feats:
        st.warning("Parada não encontrada no grafo.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Índice de risco", f"{feats['risk_score_normalized']:.0f} / 100")
        c2.metric("Reclamações (componente)", f"{feats['risk_score_atual'] * 100:.0f} / 100")
        c3.metric("Tiroteio, score do modelo", f"{feats['risk_score_tiroteio'] * 100:.0f} / 100")
        with c4:
            st.markdown("<div class='rm-muted' style='margin-bottom:6px'>Nível</div>"
                        + risk_badge(feats.get("risk_level")), unsafe_allow_html=True)
        order = meta["features"]
        rows = [{"Variável": FEATURE_LABELS.get(f, f), "Nome técnico": f,
                 "Valor": round(float(feats.get(f, 0) or 0), 4)} for f in order]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=420)
        st.caption("Antes da predição: log1p nas 9 contagens de reclamações e StandardScaler em todas as 16 variáveis.")

with tab2:
    st.markdown("<p class='rm-muted'>Escolha uma parada e altere as contagens de reclamações para ver como o score do modelo muda.</p>",
                unsafe_allow_html=True)
    sim_id = st.selectbox("Parada de referência", ids, index=ids.index(sel) if sel in ids else 0,
                          format_func=lambda i: labels.get(i, i), key="sim_parada")
    base = get_stop_features_for_model(sim_id)
    if base:
        a, b = st.columns(2, gap="large")
        with a:
            st.markdown("**Reclamações em 3 e 6 meses**")
            t3 = st.slider("Total, 3 meses", 0, 500, int(base.get("total_3m", 0)))
            s3 = st.slider("Segurança Pública, 3 meses", 0, 200, int(base.get("seg_3m", 0)))
            i3 = st.slider("Iluminação Pública, 3 meses", 0, 200, int(base.get("ilum_3m", 0)))
            t6 = st.slider("Total, 6 meses", 0, 500, int(base.get("total_6m", 0)))
            s6 = st.slider("Segurança Pública, 6 meses", 0, 200, int(base.get("seg_6m", 0)))
            i6 = st.slider("Iluminação Pública, 6 meses", 0, 200, int(base.get("ilum_6m", 0)))
        with b:
            st.markdown("**Reclamações em 12 meses**")
            t12 = st.slider("Total, 12 meses", 0, 1000, int(base.get("total_12m", 0)))
            s12 = st.slider("Segurança Pública, 12 meses", 0, 400, int(base.get("seg_12m", 0)))
            i12 = st.slider("Iluminação Pública, 12 meses", 0, 400, int(base.get("ilum_12m", 0)))
            st.markdown("**Fixas da parada**")
            st.caption(f"Linhas que passam: {base['num_rotas_servindo']} · PageRank: {base['pagerank']:.6f} · "
                       f"Mês de referência: {base['mes']:02d}/{base['ano']}")
        sim = {
            "lat": base["lat"], "lon": base["lon"], "num_rotas_servindo": base["num_rotas_servindo"],
            "pagerank": base["pagerank"], "num_reclamacoes_3m": t3, "num_reclamacoes_6m": t6,
            "num_reclamacoes_12m": t12, "num_reclamacoes_seguranca_3m": s3, "num_reclamacoes_seguranca_6m": s6,
            "num_reclamacoes_seguranca_12m": s12, "num_reclamacoes_iluminacao_3m": i3,
            "num_reclamacoes_iluminacao_6m": i6, "num_reclamacoes_iluminacao_12m": i12,
            "ano": base["ano"], "mes_sin": base["mes_sin"], "mes_cos": base["mes_cos"],
        }
        p = predict(sim, model, scaler, meta)
        atual = base["risk_score_atual"]
        total = (0.6 * atual + 1.4 * p) / 2.0
        lo, hi = stops_df["risk_score_total"].min(), stops_df["risk_score_total"].max()
        norm = (total - lo) / (hi - lo) * 100 if hi != lo else 50
        level = "Alto" if norm >= 75 else "Médio-Alto" if norm >= 50 else "Médio-Baixo" if norm >= 25 else "Baixo"
        st.divider()
        r1, r2, r3 = st.columns(3)
        r1.metric("Score de tiroteio simulado", f"{p * 100:.0f} / 100",
                  delta=f"{(p - base['risk_score_tiroteio']) * 100:+.0f}")
        r2.metric("Índice de risco simulado", f"{norm:.0f} / 100")
        with r3:
            st.markdown("<div class='rm-muted' style='margin-bottom:6px'>Nível simulado</div>" + risk_badge(level),
                        unsafe_allow_html=True)
        st.caption(f"Fórmula: (0,6 × {atual * 100:.0f} + 1,4 × {p * 100:.0f}) / 2, normalizado de 0 a 100 pelas paradas atuais.")

with tab3:
    params = meta.get("best_params", {})
    hp = {"learning_rate": "Taxa de aprendizado", "max_depth": "Profundidade máxima", "n_estimators": "Número de árvores",
          "subsample": "Subamostragem", "scale_pos_weight": "Peso da classe positiva", "eval_metric": "Métrica de avaliação"}
    st.dataframe(pd.DataFrame([{"Parâmetro": v, "Valor": str(params[k])} for k, v in hp.items() if k in params]),
                 hide_index=True, width="stretch")
    st.markdown("**Artefatos em `artifacts/`:** `xgb_model.joblib`, `scaler.joblib`, `metadata.json`, `val_predictions.parquet`.")
    st.code(
        """import joblib, json, numpy as np

model = joblib.load("artifacts/xgb_model.joblib")
scaler = joblib.load("artifacts/scaler.joblib")
meta = json.load(open("artifacts/metadata.json"))

x = np.array([[...16 variáveis na ordem de meta["features"]...]])
x[0, 4:13] = np.log1p(x[0, 4:13])          # contagens de reclamações
score = model.predict_proba(scaler.transform(x))[0, 1]""",
        language="python",
    )
