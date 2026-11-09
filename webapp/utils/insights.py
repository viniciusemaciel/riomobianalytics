"""Leituras locais dos artefatos do modelo e do GTFS (sem acessar os bancos).

Usadas para as métricas da página Risco, o histórico mensal no painel da
parada e o desenho da página Início.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACTS = ROOT / "artifacts"
GTFS = ROOT / "data" / "gtfs"

FEATURE_LABELS = {
    "lat": "Latitude",
    "lon": "Longitude",
    "ano": "Ano",
    "mes_sin": "Mês (sazonalidade, seno)",
    "mes_cos": "Mês (sazonalidade, cosseno)",
    "num_rotas_servindo": "Linhas que passam na parada",
    "pagerank": "Centralidade na rede (PageRank)",
    "num_reclamacoes_3m": "Reclamações totais, 3 meses",
    "num_reclamacoes_6m": "Reclamações totais, 6 meses",
    "num_reclamacoes_12m": "Reclamações totais, 12 meses",
    "num_reclamacoes_seguranca_3m": "Reclamações de segurança, 3 meses",
    "num_reclamacoes_seguranca_6m": "Reclamações de segurança, 6 meses",
    "num_reclamacoes_seguranca_12m": "Reclamações de segurança, 12 meses",
    "num_reclamacoes_iluminacao_3m": "Reclamações de iluminação, 3 meses",
    "num_reclamacoes_iluminacao_6m": "Reclamações de iluminação, 6 meses",
    "num_reclamacoes_iluminacao_12m": "Reclamações de iluminação, 12 meses",
}


@st.cache_data(show_spinner=False)
def load_metadata() -> dict:
    with open(ARTIFACTS / "metadata.json") as f:
        return json.load(f)


@st.cache_data(show_spinner=False)
def load_val_predictions() -> pd.DataFrame:
    path = ARTIFACTS / "val_predictions.parquet"
    if not path.exists():
        return pd.DataFrame(columns=["stop_id", "ano_mes", "y_true", "y_pred_prob_xgb"])
    return pd.read_parquet(path)


@st.cache_data(show_spinner=False)
def model_metrics() -> dict:
    """Métricas de validação calculadas a partir de val_predictions.parquet."""
    from sklearn.metrics import precision_score, recall_score, roc_auc_score

    df = load_val_predictions()
    if df.empty:
        return {}
    thr = float(load_metadata().get("best_threshold", 0.5))
    y, p = df["y_true"], df["y_pred_prob_xgb"]
    deciles = (
        df.assign(dec=pd.qcut(p, 10, labels=False, duplicates="drop"))
        .groupby("dec")
        .agg(score=("y_pred_prob_xgb", "mean"), taxa=("y_true", "mean"), n=("y_true", "size"))
        .reset_index()
    )
    return {
        "auc": float(roc_auc_score(y, p)),
        "recall": float(recall_score(y, p >= thr)),
        "precision": float(precision_score(y, p >= thr)),
        "base_rate": float(y.mean()),
        "threshold": thr,
        "n": int(len(df)),
        "n_stops": int(df["stop_id"].nunique()),
        "deciles": deciles.to_dict("records"),
    }


@st.cache_data(show_spinner=False)
def feature_importance() -> list[tuple[str, str, float]]:
    """(feature, rótulo, fração do ganho) em ordem decrescente."""
    import joblib

    feats = load_metadata()["features"]
    try:
        booster = joblib.load(ARTIFACTS / "xgb_model.joblib").get_booster()
        gain = booster.get_score(importance_type="gain")
    except Exception:
        return []
    pairs = []
    for key, value in gain.items():
        name = feats[int(key[1:])] if key.startswith("f") and key[1:].isdigit() else key
        pairs.append((name, value))
    total = sum(v for _, v in pairs) or 1.0
    return sorted(
        [(n, FEATURE_LABELS.get(n, n), v / total) for n, v in pairs],
        key=lambda t: -t[2],
    )


@st.cache_data(show_spinner=False)
def stop_history(stop_id: str) -> pd.DataFrame:
    """Score mensal do modelo e meses com tiroteio para uma parada (validação 2024)."""
    df = load_val_predictions()
    out = df[df["stop_id"] == stop_id].sort_values("ano_mes")
    return out[["ano_mes", "y_pred_prob_xgb", "y_true"]].reset_index(drop=True)


@st.cache_data(show_spinner=False)
def gtfs_segments() -> pd.DataFrame:
    """Trechos entre paradas consecutivas das viagens do GTFS (lon/lat das pontas)."""
    stops = pd.read_csv(GTFS / "stops.txt", dtype=str, usecols=["stop_id", "stop_lat", "stop_lon"])
    stops["lat"] = stops["stop_lat"].astype(float)
    stops["lon"] = stops["stop_lon"].astype(float)
    st_ = pd.read_csv(GTFS / "stop_times.txt", dtype=str, usecols=["trip_id", "stop_sequence", "stop_id"])
    st_["seq"] = st_["stop_sequence"].astype(int)
    st_ = st_.sort_values(["trip_id", "seq"])
    st_["nxt"] = st_.groupby("trip_id")["stop_id"].shift(-1)
    e = st_.dropna(subset=["nxt"])[["stop_id", "nxt"]]
    e = pd.DataFrame({"a": e.min(axis=1), "b": e.max(axis=1)}).drop_duplicates()
    ll = stops.set_index("stop_id")[["lon", "lat"]]
    e = e.join(ll, on="a").join(ll, on="b", rsuffix="2").dropna()
    return e[["lon", "lat", "lon2", "lat2"]].reset_index(drop=True)


def network_art_svg(highlight: pd.DataFrame | None, w: int = 640, h: int = 440,
                    lon0: float = -43.43, lon1: float = -43.16, latc: float = -22.885) -> str:
    """Desenho da rede de ônibus (GTFS) com as paradas de nível Alto em laranja."""
    k = math.cos(math.radians(22.9))
    sx = w / ((lon1 - lon0) * k)

    def P(lon, lat):
        return (lon - lon0) * k * sx, h / 2 - (lat - latc) * sx

    seg = gtfs_segments()
    x1, y1 = P(seg["lon"].values, seg["lat"].values)
    x2, y2 = P(seg["lon2"].values, seg["lat2"].values)
    keep = (np.hypot(x2 - x1, y2 - y1) < 22) & (x1 > -10) & (x1 < w + 10) & (y1 > -10) & (y1 < h + 10)
    lines = "".join(
        f'<line x1="{a:.1f}" y1="{b:.1f}" x2="{c:.1f}" y2="{d:.1f}"/>'
        for a, b, c, d in zip(x1[keep], y1[keep], x2[keep], y2[keep])
    )
    dots = ""
    if highlight is not None and not highlight.empty:
        hx, hy = P(highlight["lon"].values, highlight["lat"].values)
        ok = (hx > 0) & (hx < w) & (hy > 0) & (hy < h)
        dots = "".join(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="2.4"/>' for a, b in zip(hx[ok], hy[ok]))
    return (
        f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="Rede de ônibus da Zona Norte e do Centro do Rio">'
        f'<defs><pattern id="rmdots" width="14" height="14" patternUnits="userSpaceOnUse">'
        f'<circle cx="1" cy="1" r="1" fill="#D3D9E1"/></pattern></defs>'
        f'<rect width="{w}" height="{h}" fill="url(#rmdots)"/>'
        f'<g stroke="#0B1F3A" stroke-opacity=".26" stroke-width=".7" stroke-linecap="round">{lines}</g>'
        f'<g fill="#F26A4B" fill-opacity=".9">{dots}</g></svg>'
    )
