"""Ferramentas de dados do assistente (fixas, só leitura).

Cada ferramenta chama funções que já existem em `webapp/utils/data_fetchers.py`
(herdando o cache de 5 minutos) e devolve `{"dados", "fonte", "detalhe"}`.

Regras comuns:
  - no máximo `MAX_LINHAS` linhas voltam ao modelo; se houve corte, `dados`
    informa `total` e `cortado`;
  - risco sempre como índice de 0 a 100 (`risk_score_normalized`), nunca "%";
    o índice de tiroteio (0 a 1 no banco) também sai de 0 a 100;
  - o app só lê o Neo4j; nada aqui toca o MongoDB;
  - erros sobem como exceção e o agente os devolve ao modelo como texto curto.

Tiroteios: `tiroteios_parada` é a única ferramenta que lê o CSV do Fogo Cruzado
(via utils/insights.py), porque as ocorrências não estão no Neo4j. Conta
ocorrências, não vítimas, e informa sempre o período que a base cobre.

Cypher livre: `consulta_cypher` roda Cypher escrito pelo modelo, só depois de
passar por `cypher_guard.validar` (leitura, lista branca, LIMIT, caminhos curtos)
e com timeout. Fica para o que as ferramentas fixas não cobrem.

Bairro: `Stop.bairro` é o bairro oficial (Limite de Bairros da Prefeitura),
gravado por scripts/09_bairro_paradas.py. Sem ele, as ferramentas de bairro
devolvem um erro explicando o que falta.
"""
from __future__ import annotations

import unicodedata

import pandas as pd

from webapp.rag import cypher_guard
from webapp.utils import data_fetchers as df_
from webapp.utils import insights
from webapp.utils.db_connections import query_neo4j, somente_leitura

MAX_LINHAS = 50
ORDENS_BAIRRO = {"paradas_nivel_alto": "paradas_nivel_alto", "indice_medio": "indice_medio", "paradas": "paradas"}
ORDENS_LINHA = {"risco_medio": "avg_risk", "paradas_alto_risco": "high_risk_stops", "total_paradas": "total_stops"}


# ----------------------------------------------------------------- utilitários
def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return s.lower().strip()


def _lim(valor, padrao: int, maximo: int = MAX_LINHAS) -> int:
    try:
        n = int(valor)
    except (TypeError, ValueError):
        n = padrao
    return max(1, min(n, maximo))


def _num(x, casas=1):
    try:
        if x is None or pd.isna(x):
            return None
        return round(float(x), casas)
    except (TypeError, ValueError):
        return None


def _cortar(df: pd.DataFrame, limite: int) -> dict:
    return {"total": int(len(df)), "cortado": bool(len(df) > limite),
            "linhas": df.head(limite).to_dict("records")}


def _parada(r) -> dict:
    return {
        "stop_id": r.get("id"),
        "nome": r.get("name"),
        "bairro": r.get("bairro") if pd.notna(r.get("bairro")) else None,
        "indice_risco": _num(r.get("risk_score_normalized")),
        "nivel": r.get("risk_level"),
        "reclamacoes": int(r.get("total_complaints") or 0),
    }


# ------------------------------------------------------------------ ferramentas
def estatisticas_gerais() -> dict:
    s = df_.get_system_stats() or {}
    return {
        "dados": {
            "paradas": s.get("total_stops"),
            "linhas": s.get("total_routes"),
            "reclamacoes_total": s.get("total_complaints"),
            "reclamacoes_abertas": s.get("open_complaints"),
            "indice_risco_medio": _num(s.get("avg_risk")),
            "paradas_nivel_alto": s.get("high_risk_stops"),
            "paradas_indice_tiroteio_ge_50": s.get("high_tiroteio_stops"),
            "escala": "índice de risco de 0 a 100; é uma previsão do modelo, não um fato observado",
        },
        "fonte": "Neo4j: totais de Stop, Route e Reclamacao",
    }


def paradas_mais_criticas(limite=10) -> dict:
    n = _lim(limite, 10)
    todas = df_.get_stops_with_risk()  # já vem ordenada por índice, do maior para o menor
    linhas = [_parada(r) for r in todas.head(n).to_dict("records")]
    return {"dados": {"paradas": linhas}, "fonte": f"Neo4j: {n} paradas de maior índice de risco"}


def buscar_parada(termo: str | None = None, bairro: str | None = None, limite=10) -> dict:
    t, bq = _norm(termo), _norm(bairro)
    if len(t) < 2 and len(bq) < 2:
        raise ValueError("informe termo (parte do nome da parada) e/ou bairro, com pelo menos 2 letras")
    n = _lim(limite, 10)
    achadas = df_.get_stops_with_risk()
    if len(t) >= 2:
        achadas = achadas[achadas["name"].map(_norm).str.contains(t, regex=False)]
    if len(bq) >= 2:
        _exige_bairro(achadas)
        achadas = achadas[achadas["bairro"].map(_norm).str.contains(bq, regex=False)]
    linhas = [_parada(r) for r in achadas.head(n).to_dict("records")]
    filtros = " e ".join(x for x in (f'nome "{termo}"' if len(t) >= 2 else "", f'bairro "{bairro}"' if len(bq) >= 2 else "") if x)
    return {"dados": {"total_encontradas": int(len(achadas)), "paradas": linhas},
            "fonte": f"Neo4j: paradas com {filtros}"}


def _exige_bairro(df: pd.DataFrame):
    if "bairro" not in df.columns or df["bairro"].notna().sum() == 0:
        raise ValueError("o bairro das paradas ainda não está no banco (falta rodar scripts/09_bairro_paradas.py --gravar)")


def resumo_bairros(ordenar_por="paradas_nivel_alto", limite=10, busca: str | None = None) -> dict:
    n = _lim(limite, 10)
    todas = df_.get_stops_with_risk()
    _exige_bairro(todas)
    g = (todas.dropna(subset=["bairro"]).groupby("bairro")
         .agg(paradas=("id", "count"), indice_medio=("risk_score_normalized", "mean"),
              paradas_nivel_alto=("risk_level", lambda s: int((s == "Alto").sum())),
              reclamacoes=("total_complaints", "sum")).reset_index())
    if busca:
        g = g[g["bairro"].map(_norm).str.contains(_norm(busca), regex=False)]
    col = ORDENS_BAIRRO.get(ordenar_por, "paradas_nivel_alto")
    g = g.sort_values(col, ascending=False)
    linhas = [{"bairro": r["bairro"], "paradas": int(r["paradas"]), "paradas_nivel_alto": int(r["paradas_nivel_alto"]),
               "indice_medio": _num(r["indice_medio"]), "reclamacoes": int(r["reclamacoes"])}
              for r in g.head(n).to_dict("records")]
    return {"dados": {"total_bairros": int(len(g)), "ordenado_por": ordenar_por, "bairros": linhas},
            "fonte": "Neo4j: paradas agrupadas por bairro oficial (Limite de Bairros da Prefeitura)"}


def detalhes_parada(stop_id: str) -> dict:
    d = df_.get_stop_details(stop_id)
    if not d:
        raise ValueError(f"parada {stop_id} não encontrada")
    linhas = df_.get_stop_routes(stop_id)
    f = df_.get_stop_features_for_model(stop_id) or {}
    return {
        "dados": {
            "stop_id": d["id"], "nome": d["name"], "bairro": d.get("bairro"), "lat": _num(d["lat"], 5), "lon": _num(d["lon"], 5),
            "indice_risco": _num(d["risk_score_normalized"]),
            "nivel": d["risk_level"],
            "indice_tiroteio": _num((d["risk_score_tiroteio"] or 0) * 100),
            "indice_reclamacoes": _num((d["risk_score_atual"] or 0) * 100),
            "reclamacoes_total": int(d["total_complaints"] or 0),
            "reclamacoes_abertas": int(d["open_complaints"] or 0),
            "acessivel_cadeira_de_rodas": d.get("wheelchair_accessible"),
            "tiroteios_a_500m": None if d.get("tiroteios_500m_total") is None else {
                "base_toda": d.get("tiroteios_500m_total"), "ultimos_12_meses_da_base": d.get("tiroteios_500m_12m"),
                "base_termina_em": d.get("tiroteios_base_fim"),
                "regra": "exposição: um tiroteio conta para todas as paradas a até 500 m; não some paradas"},
            "linhas": [{"id": r["id"], "numero": r["short_name"], "nome": r["long_name"]}
                       for r in linhas.head(MAX_LINHAS).to_dict("records")],
            "total_linhas": int(len(linhas)),
            "pagerank": _num(f.get("pagerank"), 6),
            "reclamacoes_3m_6m_12m": [f.get("total_3m"), f.get("total_6m"), f.get("total_12m")],
            "seguranca_publica_3m_6m_12m": [f.get("seg_3m"), f.get("seg_6m"), f.get("seg_12m")],
            "iluminacao_3m_6m_12m": [f.get("ilum_3m"), f.get("ilum_6m"), f.get("ilum_12m")],
        },
        "fonte": f"Neo4j: parada {d['name']} ({stop_id})",
    }


def reclamacoes_parada(stop_id: str, limite=15) -> dict:
    n = _lim(limite, 15)
    df = df_.get_stop_complaints(stop_id)
    if df.empty:
        return {"dados": {"total": 0, "por_servico": {}, "recentes": []},
                "fonte": f"Neo4j: reclamações ligadas à parada {stop_id}"}
    recentes = df.head(n).copy()
    recentes["descricao"] = recentes["descricao"].fillna("").str.slice(0, 200)
    cols = ["protocolo", "data_abertura", "servico", "status", "criticidade", "bairro", "descricao"]
    return {
        "dados": {"total": int(len(df)),
                  "por_servico": df["servico"].value_counts().to_dict(),
                  "recentes": recentes[cols].to_dict("records")},
        "fonte": f"Neo4j: reclamações do 1746 ligadas à parada {stop_id}",
    }


def tiroteios_parada(stop_id: str, meses=12) -> dict:
    m = _lim(meses, 12, 36)
    d = df_.get_stop_details(stop_id)
    if not d:
        raise ValueError(f"parada {stop_id} não encontrada")
    periodo = insights.shootings_periodo()
    serie = insights.shootings_by_month(float(d["lat"]), float(d["lon"]), 500, m)
    if periodo is None or serie.empty:
        raise ValueError("a base de ocorrências do Fogo Cruzado não foi encontrada")
    por_mes = [{"mes": str(p), "ocorrencias": int(n)} for p, n in zip(serie["mes"], serie["n"])]
    total = sum(x["ocorrencias"] for x in por_mes)
    return {
        "dados": {
            "parada": d["name"], "stop_id": stop_id, "raio_metros": 500,
            "janela": {"primeiro_mes": por_mes[0]["mes"], "ultimo_mes": por_mes[-1]["mes"], "meses": len(por_mes)},
            "periodo_coberto_pela_base": {"primeiro_mes": periodo[0], "ultimo_mes": periodo[1]},
            "total_ocorrencias": total,
            "meses_com_ocorrencia": sum(1 for x in por_mes if x["ocorrencias"] > 0),
            "por_mes": por_mes,
            "observacao": ("Conta ocorrências do Fogo Cruzado, não vítimas. A janela termina no último mês da base, "
                           "não em hoje. É histórico; o índice de risco é uma previsão e pode divergir da contagem."),
        },
        "fonte": f"Fogo Cruzado (CSV do projeto): ocorrências a até 500 m de {d['name']}, {por_mes[0]['mes']} a {por_mes[-1]['mes']}",
    }


def tiroteios_bairros(ano_inicio=None, ano_fim=None, limite=10, busca: str | None = None) -> dict:
    """Tiroteios por bairro oficial, cada ocorrência contada uma vez (nós Tiroteio do scripts/10)."""
    n = _lim(limite, 10, 170)
    periodo = query_neo4j("MATCH (t:Tiroteio) RETURN min(t.mes) AS ini, max(t.mes) AS fim, count(t) AS n")
    if not periodo or not periodo[0]["n"]:
        raise ValueError("os tiroteios ainda não estão no grafo (falta rodar scripts/10_tiroteios_neo4j.py --gravar)")
    ini, fim = periodo[0]["ini"], periodo[0]["fim"]
    a0 = _lim(ano_inicio, int(ini[:4]), 2100) if ano_inicio else int(ini[:4])
    a1 = _lim(ano_fim, int(fim[:4]), 2100) if ano_fim else int(fim[:4])
    linhas = query_neo4j("""
        MATCH (t:Tiroteio) WHERE t.bairro IS NOT NULL AND t.ano >= $a0 AND t.ano <= $a1
        RETURN t.bairro AS bairro, count(t) AS ocorrencias ORDER BY ocorrencias DESC
    """, {"a0": a0, "a1": a1})
    total_rio = sum(r["ocorrencias"] for r in linhas)
    n_bairros = len(linhas)
    for pos, r in enumerate(linhas, 1):  # posição no ranking geral, antes do filtro de busca
        r["posicao"] = pos
    if busca:
        linhas = [r for r in linhas if _norm(busca) in _norm(r["bairro"])]
    return {
        "dados": {"anos": [a0, a1], "periodo_coberto_pela_base": {"primeiro_mes": ini, "ultimo_mes": fim},
                  "total_no_municipio": total_rio, "bairros_com_ocorrencia": n_bairros, "bairros": linhas[:n],
                  "observacao": ("Cada ocorrência conta uma vez, no bairro oficial onde caiu (só município do Rio). "
                                 "Conta ocorrências, não vítimas. O ano final pode estar incompleto se a base terminar antes de dezembro.")},
        "fonte": f"Fogo Cruzado no Neo4j: ocorrências por bairro oficial, {a0} a {a1}",
    }


def resumo_reclamacoes() -> dict:
    # Cypher próprio: get_complaints_summary lê o MongoDB, e o assistente só usa o Neo4j.
    por_servico = query_neo4j("""
        MATCH (rec:Reclamacao)
        RETURN COALESCE(rec.servico, 'Sem categoria') AS categoria, count(rec) AS total,
               count(CASE WHEN rec.status = 'Aberto' THEN 1 END) AS abertas
        ORDER BY total DESC LIMIT 50
    """)
    total = sum(r["total"] for r in por_servico)
    return {"dados": {"total": total, "por_categoria": por_servico},
            "fonte": "Neo4j: contagem de Reclamacao por categoria (serviço do 1746)"}


def metricas_linhas(ordenar_por="risco_medio", limite=10, busca: str | None = None) -> dict:
    n = _lim(limite, 10)
    col = ORDENS_LINHA.get(ordenar_por, "avg_risk")
    df = df_.get_routes_with_metrics()
    if busca:
        b = _norm(busca)
        df = df[df["name"].map(_norm).str.contains(b, regex=False) | df["full_name"].map(_norm).str.contains(b, regex=False)]
    df = df.sort_values(col, ascending=False)
    linhas = [{"id": r["id"], "numero": r["name"], "nome": r["full_name"],
               "indice_risco_medio": _num(r["avg_risk"]), "paradas": int(r["total_stops"] or 0),
               "paradas_nivel_alto": int(r["high_risk_stops"] or 0)} for r in df.head(n).to_dict("records")]
    return {"dados": {"total_linhas": int(len(df)), "ordenado_por": ordenar_por, "linhas": linhas},
            "fonte": "Neo4j: métricas por linha (índice médio das paradas atendidas)"}


def rede_em_volta(stop_id: str, saltos=1, limite=15) -> dict:
    h = _lim(saltos, 1, 3)
    n = _lim(limite, 15)
    viz = df_.get_connected_stops(stop_id, h)
    if viz.empty:
        return {"dados": {"total": 0, "paradas": []}, "fonte": f"Neo4j: conexões da parada {stop_id}"}
    indice = df_.get_stops_with_risk().set_index("id")["risk_score_normalized"]
    viz = viz.drop_duplicates("id").copy()
    viz["indice_risco"] = viz["id"].map(indice)
    viz = viz.sort_values("indice_risco", ascending=False)
    linhas = [{"stop_id": r["id"], "nome": r["name"], "indice_risco": _num(r["indice_risco"]),
               "nivel": r["risk_level"], "reclamacoes": int(r["total_complaints"] or 0)}
              for r in viz.head(n).to_dict("records")]
    ind_medio = _num(viz["indice_risco"].mean())
    return {"dados": {"saltos": h, "total": int(len(viz)), "indice_medio_vizinhas": ind_medio, "paradas": linhas},
            "fonte": f"Neo4j: paradas a até {h} salto(s) de {stop_id} (CONNECTS_TO; a consulta devolve no máximo 50)"}


MAX_CHARS_VALOR = 300  # texto longo (ex.: descrição de reclamação) é cortado na consulta livre


def _enxugar(v):
    if isinstance(v, str):
        return v if len(v) <= MAX_CHARS_VALOR else v[:MAX_CHARS_VALOR] + "…"
    if isinstance(v, dict):
        return {k: _enxugar(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_enxugar(x) for x in v[:MAX_LINHAS]]
    if isinstance(v, float):
        return round(v, 4)
    return v


def consulta_cypher(consulta: str, objetivo: str | None = None) -> dict:
    v = cypher_guard.validar(consulta)  # CypherBloqueado volta ao modelo como erro, com o motivo
    try:
        linhas = query_neo4j(v.consulta, timeout=cypher_guard.TIMEOUT_S)
    except Exception as e:
        msg = str(e)
        if "TimedOut" in msg or "timed out" in msg.lower() or "Timeout" in type(e).__name__:
            raise ValueError(f"a consulta passou de {cypher_guard.TIMEOUT_S} s e foi cancelada. "
                             "Filtre antes (por bairro, nível ou id) e agregue com count/avg.") from e
        if "access mode" in msg.lower() or "AccessMode" in msg:
            raise ValueError("o banco recusou: a consulta tentou escrever, e o assistente só lê.") from e
        raise ValueError(f"o Neo4j recusou a consulta: {msg[:250]}") from e
    linhas = [_enxugar(l) for l in linhas]
    descricao = (objetivo or "").strip()[:120] or "consulta livre"
    return {
        "dados": {"linhas": linhas, "total_linhas": len(linhas), "limite": v.limite,
                  "pode_haver_mais": len(linhas) >= v.limite and v.limite > 0, "avisos": v.avisos},
        "fonte": f"Neo4j (consulta livre): {descricao}",
        "detalhe": v.consulta,
    }


# ------------------------------------------------------------ definições e despacho
def _tool(nome, descricao, props: dict, obrigatorios=()):
    return {"name": nome, "description": descricao,
            "input_schema": {"type": "object", "properties": props, "required": list(obrigatorios)}}


_STOP_ID = {"type": "string", "description": "id da parada (campo stop_id devolvido por outras ferramentas)"}
_LIMITE = {"type": "integer", "description": f"máximo de itens (1 a {MAX_LINHAS})"}

DEFINICOES = [
    _tool("estatisticas_gerais",
          "Totais do projeto: paradas, linhas, reclamações, índice de risco médio e paradas de nível alto.", {}),
    _tool("paradas_mais_criticas",
          "Paradas com maior índice de risco (0 a 100), em ordem decrescente.", {"limite": _LIMITE}),
    _tool("buscar_parada",
          "Busca paradas pelo nome (ou parte dele) e/ou pelo bairro oficial; devolve índice de risco, nível, bairro e "
          "stop_id. Use antes das ferramentas que pedem stop_id.",
          {"termo": {"type": "string", "description": "parte do nome da parada"},
           "bairro": {"type": "string", "description": "nome do bairro (ou parte dele)"}, "limite": _LIMITE}),
    _tool("resumo_bairros",
          "Bairros ordenados por número de paradas de nível alto, índice médio ou total de paradas, com reclamações.",
          {"ordenar_por": {"type": "string", "enum": list(ORDENS_BAIRRO), "description": "padrão: paradas_nivel_alto"},
           "limite": _LIMITE, "busca": {"type": "string", "description": "filtra pelo nome do bairro"}}),
    _tool("detalhes_parada",
          "Detalhes de uma parada: índice e nível de risco, componentes (tiroteio e reclamações), linhas que passam, "
          "PageRank e reclamações dos últimos 3, 6 e 12 meses.", {"stop_id": _STOP_ID}, ["stop_id"]),
    _tool("reclamacoes_parada",
          "Reclamações do 1746 ligadas a uma parada: total, contagem por categoria e as mais recentes.",
          {"stop_id": _STOP_ID, "limite": _LIMITE}, ["stop_id"]),
    _tool("tiroteios_parada",
          "Histórico de ocorrências de tiroteio (Fogo Cruzado) a até 500 m de uma parada, mês a mês. Conta ocorrências, não "
          "vítimas, e não traz motivo nem autoria. A janela termina no último mês da base, não em hoje: cite sempre o "
          "período devolvido. Não agrega por bairro nem por ano.",
          {"stop_id": _STOP_ID, "meses": {"type": "integer", "description": "janela em meses, de 1 a 36 (padrão 12)"}},
          ["stop_id"]),
    _tool("tiroteios_bairros",
          "Ocorrências de tiroteio (Fogo Cruzado) por bairro oficial do município do Rio, cada ocorrência contada uma vez, "
          "com filtro de anos. Use para rankings e totais por bairro; NÃO some valores de paradas para isso.",
          {"ano_inicio": {"type": "integer"}, "ano_fim": {"type": "integer"}, "limite": _LIMITE,
           "busca": {"type": "string", "description": "filtra pelo nome do bairro"}}),
    _tool("resumo_reclamacoes",
          "Contagem de reclamações do 1746 por categoria (segurança pública, iluminação etc.), no projeto todo.", {}),
    _tool("metricas_linhas",
          "Linhas de ônibus com índice de risco médio, número de paradas e de paradas de nível alto.",
          {"ordenar_por": {"type": "string", "enum": list(ORDENS_LINHA), "description": "padrão: risco_medio"},
           "limite": _LIMITE, "busca": {"type": "string", "description": "filtra por número ou nome da linha"}}),
    _tool("consulta_cypher",
          "Consulta Cypher livre, SÓ LEITURA, no Neo4j do projeto. Use apenas quando nenhuma outra ferramenta responde "
          "(cruzamentos, contagens e rankings específicos). Siga o esquema do prompt: rótulos Stop, Route, Reclamacao, "
          "Categoria; relações SERVES, CONNECTS_TO, AFFECTS, HAS_TYPE. Uma instrução, começando com MATCH/WITH/UNWIND, "
          "com RETURN e de preferência agregada; no máximo 50 linhas (LIMIT é aplicado), caminhos até *1..3, sem CALL, "
          "apoc ou escrita. Timeout de " + str(cypher_guard.TIMEOUT_S) + " s. Se der erro, leia o motivo e corrija a consulta uma vez.",
          {"consulta": {"type": "string", "description": "o Cypher, sem parâmetros ($) e sem crases"},
           "objetivo": {"type": "string", "description": "em poucas palavras, o que a consulta busca (vira o título da fonte)"}},
          ["consulta", "objetivo"]),
    _tool("rede_em_volta",
          "Paradas ligadas a uma parada na rede (CONNECTS_TO), com índice de risco de cada uma e a média da vizinhança.",
          {"stop_id": _STOP_ID, "saltos": {"type": "integer", "description": "1 a 3"}, "limite": _LIMITE}, ["stop_id"]),
]

_FUNCOES = {f.__name__: f for f in (
    estatisticas_gerais, paradas_mais_criticas, buscar_parada, resumo_bairros, detalhes_parada,
    reclamacoes_parada, tiroteios_parada, tiroteios_bairros, resumo_reclamacoes, metricas_linhas, rede_em_volta, consulta_cypher)}


def executar(nome: str, argumentos: dict | None = None) -> dict:
    fn = _FUNCOES.get(nome)
    if fn is None:
        raise ValueError(f"ferramenta desconhecida: {nome}")
    with somente_leitura():  # o Neo4j recusa qualquer escrita nesta sessão
        return fn(**(argumentos or {}))
