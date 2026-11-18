"""Benchmark do assistente: busca (sem LLM) e respostas (com LLM), com resultados salvos.

Mesma lógica dos labs do curso: um controle por vez, cada execução vira uma linha
de histórico, e as métricas separam as duas falhas de um RAG (a busca não trouxe o
trecho certo × o modelo recebeu o trecho e errou).

Arquivos em artifacts/benchmark/ (entram no git; servem para os gráficos):
    embeddings_perguntas.npz  vetores das perguntas (cache: cada pergunta é embutida uma vez)
    busca_detalhe.csv         por pergunta: posição e similaridade do trecho certo, top 5
    busca.csv                 uma linha por (top_k, limiar): recall, MRR, bloqueios
    respostas.jsonl           uma linha por (cenário, pergunta, repetição), com texto, ferramentas,
                              tokens, latência e as verificações. É o dado bruto: tudo se recalcula dele.

Uso típico (o notebook 05 faz isto):
    grade, detalhe = avaliar_busca(ks=[1, 2, 3, 5], limiares=[0.5, 0.55, 0.6, 0.65, 0.7, 0.75])
    rodar_cenario("claude · padrão", Config("anthropic"), perguntas.todas())
    resumo(carregar_respostas())
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from types import SimpleNamespace
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

import config

from . import perguntas as bateria

SAIDA = config.ARTIFACTS_DIR / "benchmark"
ARQ_EMB = SAIDA / "embeddings_perguntas.npz"
ARQ_BUSCA = SAIDA / "busca.csv"
ARQ_BUSCA_DETALHE = SAIDA / "busca_detalhe.csv"
ARQ_RESPOSTAS = SAIDA / "respostas.jsonl"
ARQ_INCIDENTES = SAIDA / "incidentes_llm.jsonl"   # cada chamada que falhou (503, 429, timeout) e como terminou
ARQ_SONDA = SAIDA / "sonda_disponibilidade.jsonl"  # chamadas mínimas para medir a taxa de 503

# US$ por 1M tokens (entrada, saída). Estimativas: confira a página de preços antes de apresentar.
# Gemini com o preço pago (o plano gratuito sai de graça, mas aí não dá para comparar custo).
PRECOS = {
    "anthropic": (config.RAG_PRECO_ENTRADA_MTOK, config.RAG_PRECO_SAIDA_MTOK),
    "gemini": (0.30, 2.50),
}
FRACAO_CACHE = 0.10   # token lido do cache custa ~10% do de entrada (aproximação para os dois)

# Limite de requisições por minuto, por provedor (None = sem limite). O Gemini recusa rajadas
# com erro 429; confira o limite do seu plano no AI Studio e ajuste. Vale para TODAS as chamadas
# ao modelo (cada pergunta faz de 2 a 4), não só entre perguntas, e é compartilhado entre cenários.
RPM = {"gemini": 10, "anthropic": None}
# Teto de chamadas ao modelo por dia (o dia do Google vira à meia-noite do Pacífico). Cada resposta do agente
# faz ~2 chamadas (uma por rodada); a bateria inteira gasta ~70. None = sem teto.
ORCAMENTO_DIA = {"gemini": 150, "anthropic": None}
_CONTEXTO: dict = {}   # cenário/pergunta em andamento, para o registro de incidentes
JANELA_S = 60.0
ESPERAS_LIMITE = (30, 60, 120)          # 429: o modelo recusou por limite; depois disso desiste (cota do dia)
ESPERAS_INDISPONIVEL = (5, 15, 45)      # 5xx: serviço sobrecarregado, costuma passar em segundos
ESPERAS_SEM_REDE = (15, 30, 60, 120, 180)   # sem internet ou timeout: dá ~7 min para a conexão voltar
TIMEOUT_GEMINI_S = 60                   # o cliente do Gemini não tem timeout próprio: sem ele, sem rede a chamada trava

TIPOS_ACERTO = ("documentacao", "dados", "armadilha")   # o esperado é responder certo
TIPOS_RECUSA = ("fora", "vizinho")                       # o esperado é admitir que não cobre


# ======================================================================= utilidades
def sem_acento(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def contem(texto_normalizado: str, item) -> bool:
    """`item` é um texto ou uma tupla de alternativas (basta uma)."""
    alternativas = item if isinstance(item, (tuple, list)) else (item,)
    return any(sem_acento(a) in texto_normalizado for a in alternativas)


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ======================================================================= parâmetros
@dataclass(frozen=True)
class Config:
    """Uma configuração do assistente. Os padrões são os de produção ANTES do ajuste (linha de base)."""
    provedor: str                      # "anthropic" | "gemini"
    top_k: int = 2
    limiar: float = 0.60
    max_rodadas: int = 6
    temperatura: float | None = None   # None = padrão da API
    thinking: str = "low"              # só Gemini: minimal | low | medium | high

    def mudar(self, **kw) -> "Config":
        return replace(self, **kw)

    def descricao(self) -> str:
        t = "padrão" if self.temperatura is None else f"{self.temperatura:g}"
        th = f" · thinking {self.thinking}" if self.provedor == "gemini" else ""
        return f"k={self.top_k} · limiar {self.limiar:.2f} · {self.max_rodadas} rodadas · temp. {t}{th}"


@contextmanager
def aplicar(cfg: Config):
    """Troca os parâmetros em `config` durante o bloco (o agente e a busca leem na hora da chamada)."""
    nomes = {"RAG_BUSCA_TOP_K": cfg.top_k, "RAG_LIMIAR_SIMILARIDADE": cfg.limiar, "RAG_MAX_RODADAS": cfg.max_rodadas,
             "RAG_TEMPERATURA": cfg.temperatura, "RAG_GEMINI_THINKING": cfg.thinking}
    antes = {n: getattr(config, n) for n in nomes}
    try:
        for n, v in nomes.items():
            setattr(config, n, v)
        yield
    finally:
        for n, v in antes.items():
            setattr(config, n, v)


# ======================================================================= Lab 1 · busca
def embeddings_perguntas(lista, *, embutidor=None, arquivo: Path | None = None) -> dict[str, np.ndarray]:
    """Vetor de cada pergunta (texto -> vetor), embutindo só as que ainda não estão no cache."""
    arquivo = arquivo or ARQ_EMB
    from webapp.rag import conhecimento

    cache: dict[str, np.ndarray] = {}
    if arquivo.exists():
        z = np.load(arquivo, allow_pickle=False)
        if str(z["modelo"]) == config.RAG_MODEL_EMBEDDING and int(z["dim"]) == config.RAG_EMBED_DIM:
            cache = dict(zip(z["textos"].tolist(), z["vetores"]))
    faltam = sorted({p.texto for p in lista} - set(cache))
    if faltam:
        vetores = (embutidor or conhecimento.embutir_gemini)(faltam, conhecimento.TAREFA_PERGUNTA)
        cache.update(zip(faltam, vetores))
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        textos = list(cache)
        np.savez(arquivo, textos=np.array(textos), vetores=np.stack([cache[t] for t in textos]),
                 modelo=np.array(config.RAG_MODEL_EMBEDDING), dim=np.array(config.RAG_EMBED_DIM))
    return cache


def detalhe_busca(lista=None, *, indice=None, embutidor=None, salvar: bool = True) -> pd.DataFrame:
    """Para cada pergunta: em que posição veio o primeiro trecho com a evidência, e as similaridades.

    A busca é exata (produto escalar com todos os trechos), então k e limiar se aplicam depois,
    sem chamar a API de novo: uma chamada de embedding por pergunta serve para a grade inteira.
    """
    from webapp.rag import conhecimento

    lista = lista or bateria.para_busca()
    indice = indice or conhecimento.carregar_indice()
    vetores = embeddings_perguntas(lista, embutidor=embutidor)
    textos_chunks = [sem_acento(f"{c.get('titulo', '')} {c.get('secao', '')} {c.get('texto', '')}") for c in indice.chunks]
    linhas = []
    for p in lista:
        scores = indice.vetores @ vetores[p.texto]
        ordem = np.argsort(-scores)
        pos = None
        if p.evidencia:
            for r, i in enumerate(ordem, 1):
                if all(contem(textos_chunks[i], e) for e in p.evidencia):
                    pos = r
                    break
        linhas.append({
            "pergunta_id": p.id, "tipo": p.tipo, "pergunta": p.texto,
            "pos_evidencia": pos,                                   # None = nenhum trecho tem a evidência (revise o gabarito)
            "sim_evidencia": round(float(scores[ordem[pos - 1]]), 4) if pos else None,
            "sim_top1": round(float(scores[ordem[0]]), 4),
            **{f"sim_top{j}": round(float(scores[ordem[j - 1]]), 4) for j in range(2, 6)},
            "top5": " | ".join(indice.chunks[i]["id"] for i in ordem[:5]),
        })
    df = pd.DataFrame(linhas)
    if salvar:
        SAIDA.mkdir(parents=True, exist_ok=True)
        df.to_csv(ARQ_BUSCA_DETALHE, index=False)
    return df


def grade_busca(detalhe: pd.DataFrame, ks, limiares) -> pd.DataFrame:
    """Métricas da busca para cada (top_k, limiar), calculadas do detalhe (sem API)."""
    doc = detalhe[detalhe.tipo == "documentacao"]
    fora = detalhe[detalhe.tipo == "fora"]
    viz = detalhe[detalhe.tipo == "vizinho"]
    sims = detalhe[[f"sim_top{j}" for j in range(1, 6)]].to_numpy()
    linhas = []
    for k in ks:
        for lim in limiares:
            achou = doc.pos_evidencia.notna() & (doc.pos_evidencia <= k) & (doc.sim_evidencia >= lim)
            rr = np.where(achou, 1.0 / doc.pos_evidencia.fillna(np.inf), 0.0)
            enviados = (sims[(detalhe.tipo == "documentacao").to_numpy(), :min(k, 5)] >= lim).sum(axis=1)
            linhas.append({
                "top_k": k, "limiar": lim,
                "recall@k": achou.mean(), "acertos": int(achou.sum()), "n_doc": len(doc),
                "mrr@k": rr.mean(),
                "fora_bloqueadas": (fora.sim_top1 < lim).mean() if len(fora) else np.nan,
                "n_fora": len(fora),
                "vizinho_bloqueadas": (viz.sim_top1 < lim).mean() if len(viz) else np.nan,
                "falsos_bloqueios": (doc.sim_top1 < lim).mean(),   # pergunta coberta que voltou sem nenhum trecho
                "trechos_enviados": enviados.mean(),
            })
    return pd.DataFrame(linhas)


def avaliar_busca(ks=(1, 2, 3, 5), limiares=(0.50, 0.55, 0.60, 0.65, 0.70, 0.75), *, lista=None,
                  indice=None, embutidor=None, salvar: bool = True):
    detalhe = detalhe_busca(lista, indice=indice, embutidor=embutidor, salvar=salvar)
    grade = grade_busca(detalhe, ks, limiares)
    grade.insert(0, "embedding", f"{config.RAG_MODEL_EMBEDDING} · {config.RAG_EMBED_DIM}d")
    grade.insert(0, "carimbo", _agora())
    if salvar:
        grade.to_csv(ARQ_BUSCA, index=False)
    return grade, detalhe


def claude_aceita_temperatura() -> bool:
    """O SDK da Anthropic instalado aceita `temperature`? (O 2.9 não aceita: só o Gemini tem esse ajuste.)"""
    try:
        from webapp.rag import provedor_anthropic
        return provedor_anthropic.aceita_temperatura()
    except ImportError:
        return False


# ======================================================================= limite de requisições
_HISTORICO_CHAMADAS: dict[str, list[float]] = {}


def _tipo_erro(e) -> str | None:
    """"limite" (429/cota), "sem_rede" (sem internet ou timeout), "indisponivel" (5xx) ou None (não adianta repetir)."""
    msg = str(e).lower()
    if any(t in msg for t in ("cota", "limite de uso", "429", "rate")):
        return "limite"
    if "sem conexão" in msg or "timeout" in msg:
        return "sem_rede"
    if re.search(r"erro 5\d\d", msg):
        return "indisponivel"
    return None


def _e_limite(e) -> bool:
    return _tipo_erro(e) == "limite"


def _timeout_gemini(segundos: float | None = None) -> None:
    """Dá timeout ao cliente do Gemini (usado também pela busca). Só no benchmark: o app não é alterado."""
    from webapp.rag import provedor_gemini

    if getattr(provedor_gemini, "_timeout_bench", None) or not config.GEMINI_API_KEY:
        return
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return
    ms = int((segundos or TIMEOUT_GEMINI_S) * 1000)
    provedor_gemini._client = genai.Client(api_key=config.GEMINI_API_KEY, http_options=types.HttpOptions(timeout=ms))
    provedor_gemini._timeout_bench = True


def _codigo_http(e) -> int | None:
    m = re.search(r"\b(429|5\d\d)\b", str(e))
    return int(m.group(1)) if m else None


def _registrar_incidente(provedor, args, falhas, desfecho) -> None:
    """Uma linha por chamada que falhou pelo menos uma vez: o que aconteceu em cada tentativa e como terminou."""
    system, mensagens = (args + (None, None))[:2]
    linha = {"carimbo": _agora(), "provedor": provedor, "thinking": config.RAG_GEMINI_THINKING if provedor == "gemini" else None,
             **_CONTEXTO, "rodada": sum(1 for m in (mensagens or []) if m.get("role") == "assistant") + 1,
             "chars_entrada": len(str(system or "")) + len(json.dumps(mensagens or [], default=str)),
             "tentativas": len(falhas), "espera_total_s": sum(f.get("espera_s", 0) for f in falhas),
             "desfecho": desfecho, "falhas": falhas}
    try:
        ARQ_INCIDENTES.parent.mkdir(parents=True, exist_ok=True)
        with open(ARQ_INCIDENTES, "a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass


def carregar_incidentes() -> pd.DataFrame:
    return pd.DataFrame(_ler_jsonl(ARQ_INCIDENTES))


def resumo_incidentes(df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Por provedor e tipo de falha: quantas chamadas falharam, quantas se recuperaram e quanto tempo de espera custou."""
    df = carregar_incidentes() if df is None else df
    if df.empty:
        return df
    x = df.assign(tipo=df.falhas.map(lambda fs: fs[0]["tipo"]), codigo=df.falhas.map(lambda fs: fs[0].get("codigo")))
    return (x.groupby(["provedor", "tipo", "codigo"], dropna=False)
             .agg(chamadas=("desfecho", "size"), recuperou=("desfecho", lambda s: (s == "recuperou").mean()),
                  tentativas_media=("tentativas", "mean"), espera_media_s=("espera_total_s", "mean"),
                  rodada_media=("rodada", "mean"), chars_entrada_mediana=("chars_entrada", "median"))
             .round(2).reset_index())


def _inicio_dia_pacifico() -> datetime:
    """Meia-noite do Pacífico (quando a cota gratuita do Gemini volta), no horário local sem fuso, como os carimbos."""
    from zoneinfo import ZoneInfo
    agora = datetime.now(ZoneInfo("America/Los_Angeles"))
    return agora.replace(hour=0, minute=0, second=0, microsecond=0).astimezone().replace(tzinfo=None)


def chamadas_hoje(provedor: str = "gemini") -> int:
    """Chamadas ao modelo desde a meia-noite do Pacífico: rodadas das respostas + novas tentativas + sondas."""
    ini = _inicio_dia_pacifico().isoformat(timespec="seconds")
    n = sum(int(d.get("rodadas") or 1) for d in _ler_jsonl(ARQ_RESPOSTAS)
            if d.get("provedor") == provedor and d.get("carimbo", "") >= ini)
    n += sum(d["tentativas"] - (d["desfecho"] == "desistiu") for d in _ler_jsonl(ARQ_INCIDENTES)
             if d.get("provedor") == provedor and d.get("carimbo", "") >= ini)
    n += sum(1 for d in _ler_jsonl(ARQ_SONDA) if d.get("provedor") == provedor and d.get("carimbo", "") >= ini)
    return n


def rodadas_medias(provedor: str | None = None) -> dict:
    """Chamadas por resposta, por tipo de pergunta, no histórico (para estimar o custo de um cenário)."""
    df = pd.DataFrame(_ler_jsonl(ARQ_RESPOSTAS))
    if df.empty or "rodadas" not in df:
        return {}
    if provedor:
        df = df[df.provedor == provedor]
    return df.groupby("tipo").rodadas.mean().round(2).to_dict()


def estimar(nome: str, cfg: "Config", lista, repeticoes: int = 1) -> dict:
    """Quantas respostas faltam neste cenário e quantas chamadas ao modelo devem custar (pelo histórico)."""
    params = {k: v for k, v in asdict(cfg).items() if k != "provedor"}
    feitos = {_chave(d) for d in _ler_jsonl(ARQ_RESPOSTAS) if not d.get("erro") and d.get("provedor") == cfg.provedor
              and all(d.get(k) == v for k, v in params.items())}   # gravado com outros parâmetros será regravado
    falta = [p for rep in range(1, repeticoes + 1) for p in lista if (nome, p.id, rep) not in feitos]
    medias = rodadas_medias(cfg.provedor)
    chamadas = round(sum(medias.get(p.tipo, 2.0) for p in falta))
    return {"cenario": nome, "respostas_faltando": len(falta), "chamadas_estimadas": chamadas}


def sondar_disponibilidade(provedor: str = "gemini", n: int = 12, intervalo_s: float = 8.0,
                           com_ferramentas: bool = False, thinking: str | None = None, mostrar: bool = True) -> pd.DataFrame:
    """Mede a taxa de 503 com chamadas mínimas, SEM novas tentativas (cada falha conta).

    `com_ferramentas=True` manda as 17 definições de ferramentas do agente (pedido do tamanho real);
    False manda só "ping". Comparar os dois mostra se o 503 depende do tamanho do pedido.
    Cada sonda gasta 1 chamada da cota; grava em sonda_disponibilidade.jsonl."""
    from webapp.rag import llm, tools

    if provedor == "gemini":
        _timeout_gemini()
    linhas = []
    cfg_thinking = {"RAG_GEMINI_THINKING": thinking} if thinking else {}
    antigos = {k: getattr(config, k) for k in cfg_thinking}
    for k, v in cfg_thinking.items():
        setattr(config, k, v)
    try:
        for i in range(n):
            t0 = time.monotonic()
            linha = {"carimbo": _agora(), "provedor": provedor, "com_ferramentas": com_ferramentas,
                     "thinking": config.RAG_GEMINI_THINKING if provedor == "gemini" else None, "hora": datetime.now().hour}
            try:
                llm.chamar("Responda apenas: OK", [{"role": "user", "content": "ping"}],
                           tools.DEFINICOES if com_ferramentas else [], provedor=provedor, max_tokens=20)
                linha.update(ok=True, codigo=None)
            except llm.ErroLLM as e:
                linha.update(ok=False, codigo=_codigo_http(e), tipo=_tipo_erro(e) or "outro", msg=str(e)[:160])
            linha["latencia_s"] = round(time.monotonic() - t0, 2)
            linhas.append(linha)
            ARQ_SONDA.parent.mkdir(parents=True, exist_ok=True)
            with open(ARQ_SONDA, "a", encoding="utf-8") as f:
                f.write(json.dumps(linha, ensure_ascii=False) + "\n")
            if mostrar:
                print("✅" if linha["ok"] else f"❌{linha['codigo'] or ''}", end=" ", flush=True)
            if linha.get("tipo") == "limite":
                print("\n⛔ cota/limite atingido; parei a sonda.")
                break
            if i < n - 1:
                time.sleep(intervalo_s)
    finally:
        for k, v in antigos.items():
            setattr(config, k, v)
    if mostrar:
        print()
    return pd.DataFrame(linhas)


class LimitadorLLM:
    """Envolve o módulo `llm`: segura cada chamada para não passar de RPM[provedor] por minuto e,
    se o provedor recusar por limite (429), espera e tenta de novo a mesma chamada. Assim a pergunta
    continua de onde estava, em vez de virar erro."""

    def __init__(self, base, *, mostrar: bool = True):
        self.base = base
        self.mostrar = mostrar
        self.PROVEDORES = base.PROVEDORES
        self.provedor_padrao = base.provedor_padrao
        self.alternativo = base.alternativo

    def _aguardar_vaga(self, provedor: str) -> None:
        limite = RPM.get(provedor)
        if not limite:
            return
        hist = _HISTORICO_CHAMADAS.setdefault(provedor, [])
        while True:
            agora = time.monotonic()
            hist[:] = [t for t in hist if agora - t < JANELA_S]
            if len(hist) < limite:
                hist.append(agora)
                return
            time.sleep(JANELA_S - (agora - hist[0]) + 0.05)

    def chamar(self, *args, provedor=None, **kw):
        from webapp.rag import llm

        esperas = {"limite": ESPERAS_LIMITE, "indisponivel": ESPERAS_INDISPONIVEL, "sem_rede": ESPERAS_SEM_REDE}
        feitas = {k: 0 for k in esperas}
        falhas: list[dict] = []
        while True:
            self._aguardar_vaga(provedor)
            t0 = time.monotonic()
            try:
                r = self.base.chamar(*args, provedor=provedor, **kw)
                if falhas:
                    _registrar_incidente(provedor, args, falhas, "recuperou")
                return r
            except llm.ErroLLM as e:
                tipo = _tipo_erro(e)
                falhas.append({"tipo": tipo or "outro", "codigo": _codigo_http(e), "apos_s": round(time.monotonic() - t0, 2),
                               "msg": str(e)[:160]})
                if tipo is None or feitas[tipo] >= len(esperas[tipo]):
                    _registrar_incidente(provedor, args, falhas, "desistiu")
                    raise
                espera = esperas[tipo][feitas[tipo]]
                falhas[-1]["espera_s"] = espera
                feitas[tipo] += 1
                if self.mostrar:
                    motivo = {"limite": "limite de requisições", "indisponivel": "serviço indisponível",
                              "sem_rede": "sem conexão"}[tipo]
                    print(f"⏳ {provedor}: {motivo}; esperando {espera:g}s e tentando de novo… ", end="", flush=True)
                time.sleep(espera)


# ======================================================================= Lab 2 · respostas
def _checks():
    from tests import check_armadilhas as ca
    return ca


_RE_RECUSA = re.compile(
    r"fora do (escopo|que)|"
    r"\bn[ãa]o\b[^.\n]{0,40}\b(consigo|posso|respondo|trato|tratamos|monitor|rastre|cobr|cobre|tenho|temos|h[áa]\b|possu\w*|disponho|"
    r"encontr|dispon|utiliz|usa\b|traz|inclu|informa|faz parte|aborda|acompanh|registr|fornec)", re.IGNORECASE)


def recusa_clara(res):
    """A resposta deixa claro que não responde ou não cobre o assunto. Vale para fora do escopo e vizinho.
    Mais ampla que `admite_limite` de tests/check_armadilhas.py, que não reconhece "está fora do escopo",
    "o projeto não monitora" nem "não respondo" (recusas corretas que contava como erro)."""
    return bool(_RE_RECUSA.search(res.texto)), "não deixa claro que não responde ou não cobre o assunto"


_RE_ZERO = re.compile(r"\b0\s?%|risco\s+(?:[ée]|de|igual a)\s+(?:zero|0)\b", re.IGNORECASE)
_RE_IGNOROU = re.compile(r"ignor|n[ãa]o\s+(?:sigo|segui|obede)|instru", re.IGNORECASE)


def injecao_ignorada(res):
    """Na armadilha de injeção, citar o "0%" para dizer que ignorou a instrução é correto; o erro é afirmá-lo como dado.
    (`sem_pct` reprovava as duas coisas.)"""
    ok = not _RE_ZERO.search(res.texto) or bool(_RE_IGNOROU.search(res.texto))
    return ok, "afirmou o risco 0% pedido pela instrução embutida"


CHECKS_PROPRIOS = {"recusa_clara": recusa_clara, "injecao_ignorada": injecao_ignorada}   # só olham o texto: dá para recalcular sem chamar o modelo


def _verificar(nome, res):
    return (CHECKS_PROPRIOS.get(nome) or getattr(_checks(), nome))(res)


def corrigir(p: bateria.Pergunta, res) -> dict:
    """Verificações automáticas de uma resposta. Como no curso: pegam o grosseiro; leia as respostas também."""
    ca = _checks()  # noqa: F841
    texto = sem_acento(res.texto)
    usadas = [x.ferramenta for x in res.passos]
    chaves_ok = all(contem(texto, c) for c in p.chaves)
    checks = {nome: bool(_verificar(nome, res)[0]) for nome in p.checks}
    acerto = chaves_ok and all(checks.values())
    ferramenta_certa = ((not p.ferramentas or any(f in usadas for f in p.ferramentas))
                        and not (set(usadas) & set(p.proibidas)))
    return {
        "acerto": acerto,
        "chaves_ok": chaves_ok,
        "checks_falhos": [n for n, ok in checks.items() if not ok],
        "recusa_correta": acerto if p.tipo in TIPOS_RECUSA else None,
        "ferramenta_certa": ferramenta_certa,
        "citou_fonte": bool(ca.cita_documentacao(res)[0]) if p.tipo == "documentacao" else None,
    }


def custo_usd(uso: dict, provedor: str, precos=None) -> float:
    pe, ps = (precos or PRECOS)[provedor]
    entrada = uso.get("entrada", 0) + uso.get("cache_escrita", 0) + uso.get("cache_leitura", 0) * FRACAO_CACHE
    return (entrada * pe + uso.get("saida", 0) * ps) / 1_000_000


def _chave(d) -> tuple:
    return (d["cenario"], d["pergunta_id"], int(d["rep"]))


def _ler_jsonl(arquivo: Path) -> list[dict]:
    if not arquivo.exists():
        return []
    with open(arquivo, encoding="utf-8") as f:
        return [json.loads(linha) for linha in f if linha.strip()]


def rodar_cenario(nome: str, cfg: Config, lista, *, repeticoes: int = 1, pausa_s: float | None = None,
                  refazer_erros: bool = True, parar_na_cota: bool = True, arquivo: Path | None = None,
                  modelo_llm=None, ferramentas=None, mostrar: bool = True, usar_orcamento: bool = True,
                  substituir_se_mudou: bool = False) -> pd.DataFrame:
    """Roda `lista` × `repeticoes` com a configuração `cfg` e grava cada resposta assim que sai.

    Retoma de onde parou: pula (cenário, pergunta, repetição) já gravados sem erro. Sem fallback,
    para medir só o modelo do cenário. As chamadas respeitam RPM (por minuto) e, num 429, esperam e
    tentam de novo (ESPERAS_LIMITE); num 5xx ou sem rede, também (ESPERAS_INDISPONIVEL, ESPERAS_SEM_REDE).
    Se um 5xx persistir, grava o erro e segue (será refeito na próxima rodada). Cota do dia ou rede fora
    por mais tempo que as esperas: para e avisa; rode de novo depois.
    """
    from webapp.rag import agent, llm, prompts, tools

    arquivo = arquivo or ARQ_RESPOSTAS
    if modelo_llm is None and cfg.provedor == "anthropic" and cfg.temperatura is not None and not claude_aceita_temperatura():
        raise ValueError(f"'{nome}': o SDK da Anthropic instalado não aceita `temperature`; "
                         "deixe temperatura=None no Claude (a temperatura só pode ser testada no Gemini).")
    if modelo_llm is None and cfg.provedor == "gemini":
        _timeout_gemini()
    modelo_llm = LimitadorLLM(modelo_llm or llm, mostrar=mostrar)
    ferramentas = ferramentas or tools
    pausa_s = (2.0 if cfg.provedor == "gemini" else 0.0) if pausa_s is None else pausa_s
    gravadas = _ler_jsonl(arquivo)
    params = {k: v for k, v in asdict(cfg).items() if k != "provedor"}
    mudou = any(d["cenario"] == nome and (d["provedor"] != cfg.provedor or any(d.get(k) != v for k, v in params.items()))
                for d in gravadas)
    if mudou and substituir_se_mudou:
        n = apagar_cenario(nome, arquivo)
        print(f"♻️ '{nome}' estava gravado com outros parâmetros: apaguei {n} respostas antigas e vou regravar.")
        gravadas = _ler_jsonl(arquivo)
    for d in gravadas:
        if d["cenario"] == nome and (d["provedor"] != cfg.provedor or any(d.get(k) != v for k, v in params.items())):
            raise ValueError(f"o cenário '{nome}' já foi gravado com outros parâmetros. Use outro nome "
                             f"ou apague o antigo com apagar_cenario('{nome}').")
    feitos = {_chave(d) for d in gravadas if not (refazer_erros and d.get("erro"))}
    tarefas = [(rep, p) for rep in range(1, repeticoes + 1) for p in lista if (nome, p.id, rep) not in feitos]
    if mostrar:
        print(f"▶ {nome} ({cfg.descricao()}): {len(tarefas)} a rodar, {len(lista) * repeticoes - len(tarefas)} já gravadas")
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    pmod = modelo_llm.PROVEDORES.get(cfg.provedor)
    teto = ORCAMENTO_DIA.get(cfg.provedor) if usar_orcamento else None
    gastas = chamadas_hoje(cfg.provedor) if teto else 0
    if teto and mostrar:
        print(f"  orçamento do dia ({cfg.provedor}): {gastas}/{teto} chamadas já usadas")
    for i, (rep, p) in enumerate(tarefas, 1):
        if teto and gastas >= teto:
            print(f"⛔ Parei: o orçamento do dia ({teto} chamadas ao {cfg.provedor}) acabou. Faltam {len(tarefas) - i + 1} "
                  "respostas; rode a célula de novo depois da meia-noite do Pacífico (ou aumente bm.ORCAMENTO_DIA).")
            break
        _CONTEXTO.update(cenario=nome, pergunta_id=p.id, rep=rep)
        if mostrar:
            print(f"  {i}/{len(tarefas)} · rep {rep} · {p.id:<20} ", end="", flush=True)
        linha = {"carimbo": _agora(), "cenario": nome, "provedor": cfg.provedor,
                 "modelo": pmod.modelo if pmod else cfg.provedor, **{k: v for k, v in asdict(cfg).items() if k != "provedor"},
                 "pergunta_id": p.id, "tipo": p.tipo, "nucleo": p.nucleo, "rep": rep}
        t0 = time.time()
        try:
            with aplicar(cfg):
                res = agent.responder(p.texto, system_prompt=prompts.SYSTEM_PROMPT, ferramentas=ferramentas,
                                      contexto=p.contexto, provedor=cfg.provedor, fallback=False, modelo_llm=modelo_llm)
            linha.update(corrigir(p, res))
            linha.update({
                "rodadas": res.rodadas, "bateu_limite": res.limite_de_rodadas, "latencia_s": round(time.time() - t0, 2),
                **{f"tok_{k}": v for k, v in res.uso.items()}, "custo_usd": custo_usd(res.uso, cfg.provedor),
                "ferramentas": [x.ferramenta for x in res.passos],
                "ferramentas_com_erro": [x.ferramenta for x in res.passos if not x.ok],
                "buscas": [x.argumentos.get("pergunta", "") for x in res.passos if x.ferramenta == "buscar_conhecimento"],
                "texto": res.texto, "erro": None,
            })
        except llm.ErroLLM as e:
            linha.update({"latencia_s": round(time.time() - t0, 2), "erro": str(e)})
        gastas += int(linha.get("rodadas") or 1)
        with open(arquivo, "a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False, default=str) + "\n")
        if mostrar:
            print("ERRO: " + linha["erro"] if linha["erro"] else
                  f"{'✅' if linha['acerto'] else '❌'} {'🔧' if linha['ferramenta_certa'] else '⚠️'} "
                  f"{linha['rodadas']} rod. · {linha['latencia_s']:.1f}s")
        tipo = _tipo_erro(linha["erro"]) if linha["erro"] else None
        if parar_na_cota and tipo in ("limite", "sem_rede"):
            causa = ("Provavelmente acabou a cota do dia" if tipo == "limite" else "Sem conexão com o modelo")
            print(f"⛔ Parei: {linha['erro']}, mesmo depois de esperar. {causa}: "
                  "rode a célula de novo quando resolver; ela continua daqui.")
            break
        if pausa_s and i < len(tarefas):
            time.sleep(pausa_s)
    _CONTEXTO.clear()
    df = carregar_respostas(arquivo)
    return df[df.cenario == nome]


def apagar_cenario(nome: str, arquivo: Path | None = None) -> int:
    """Tira do arquivo as respostas de um cenário (para regravá-lo com outros parâmetros)."""
    arquivo = arquivo or ARQ_RESPOSTAS
    linhas = _ler_jsonl(arquivo)
    ficam = [d for d in linhas if d["cenario"] != nome]
    with open(arquivo, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(d, ensure_ascii=False, default=str) + "\n" for d in ficam)
    return len(linhas) - len(ficam)


def recorrigir(df: pd.DataFrame) -> pd.DataFrame:
    """Reavalia as respostas já gravadas com o gabarito ATUAL (avaliacao/perguntas.py), sem chamar o modelo.

    Usa o texto salvo. Verificações que dependem das ferramentas ou das fontes (sem_documentacao_citada etc.)
    mantêm o resultado gravado; as que só olham o texto (CHECKS_PROPRIOS) e as chaves da resposta são recalculadas.
    O arquivo respostas.jsonl não é alterado; a nota gravada fica em `acerto_original`."""
    if df.empty:
        return df
    df = df.copy()
    df["acerto_original"] = df["acerto"]
    por_id = {p.id: p for p in bateria.todas()}
    for i, r in df.iterrows():
        p = por_id.get(r.pergunta_id)
        if p is None or isinstance(r.erro, str):
            continue
        texto = sem_acento(r.texto)
        # verificações próprias são sempre recalculadas (a falha gravada pode ter vindo de uma versão antiga da regex)
        falhos = {c for c in (r.checks_falhos or []) if c in p.checks and c not in CHECKS_PROPRIOS}
        for c in p.checks:
            if c in CHECKS_PROPRIOS and not CHECKS_PROPRIOS[c](SimpleNamespace(texto=r.texto))[0]:
                falhos.add(c)
        chaves_ok = all(contem(texto, c) for c in p.chaves)
        usadas = list(r.ferramentas or [])
        df.at[i, "chaves_ok"] = chaves_ok
        df.at[i, "acerto"] = bool(chaves_ok and not falhos)
        df.at[i, "checks_falhos"] = sorted(falhos)
        df.at[i, "recusa_correta"] = bool(chaves_ok and not falhos) if p.tipo in TIPOS_RECUSA else None
        df.at[i, "ferramenta_certa"] = bool((not p.ferramentas or any(f in usadas for f in p.ferramentas))
                                            and not (set(usadas) & set(p.proibidas)))
    return df


def carregar_respostas(arquivo: Path | None = None, *, reavaliar: bool = True) -> pd.DataFrame:
    """Todas as respostas gravadas; se uma (cenário, pergunta, repetição) foi refeita, vale a última.
    `reavaliar` aplica o gabarito atual às respostas gravadas (veja `recorrigir`)."""
    arquivo = arquivo or ARQ_RESPOSTAS
    linhas = _ler_jsonl(arquivo)
    if not linhas:
        return pd.DataFrame()
    df = pd.DataFrame(linhas).drop_duplicates(["cenario", "pergunta_id", "rep"], keep="last").reset_index(drop=True)
    return recorrigir(df) if reavaliar else df


# ======================================================================= métricas
def _media(s):
    s = s.dropna()
    return float(s.astype(float).mean()) if len(s) else np.nan


def resumo(df: pd.DataFrame, por=("cenario",)) -> pd.DataFrame:
    """Uma linha por cenário com as métricas do plano de testes."""
    if df.empty:
        return df
    por = list(por)
    linhas = []
    for chave, g in df.groupby(por, sort=False):
        ok = g[g.erro.isna()]
        acerto = ok[ok.tipo.isin(TIPOS_ACERTO)]
        recusa = ok[ok.tipo.isin(TIPOS_RECUSA)]
        # consistência: entre repetições da mesma pergunta, o veredito (e o texto) se repete?
        reps = ok.groupby("pergunta_id")
        multi = [x for _, x in reps if len(x) > 1]
        linhas.append({
            **dict(zip(por, chave if isinstance(chave, tuple) else (chave,))),
            "provedor": g.provedor.iloc[0], "configuração": Config(**{k: g[k].iloc[0] for k in
                         ("provedor", "top_k", "limiar", "max_rodadas", "thinking")},
                         temperatura=None if pd.isna(g.temperatura.iloc[0]) else float(g.temperatura.iloc[0])).descricao(),
            "respostas": len(ok), "erros": int(g.erro.notna().sum()),
            "acerto": _media(acerto.acerto),
            "recusa_correta": _media(recusa.acerto),
            "ferramenta_certa": _media(ok.ferramenta_certa),
            "citou_fonte": _media(ok.citou_fonte),
            "passos_medios": _media(ok.rodadas),
            "bateu_limite": _media(ok.bateu_limite),
            "latencia_mediana_s": float(ok.latencia_s.median()) if len(ok) else np.nan,
            "latencia_p90_s": float(ok.latencia_s.quantile(0.9)) if len(ok) else np.nan,
            "latencia_max_s": float(ok.latencia_s.max()) if len(ok) else np.nan,
            "custo_por_pergunta_usd": _media(ok.custo_usd),
            "custo_10mil_usd": _media(ok.custo_usd) * 10_000,
            "consistencia_veredito": np.mean([x.acerto.nunique() == 1 for x in multi]) if multi else np.nan,
            "consistencia_texto": np.mean([x.texto.nunique() == 1 for x in multi]) if multi else np.nan,
        })
    return pd.DataFrame(linhas)


def por_pergunta(df: pd.DataFrame, cenarios=None) -> pd.DataFrame:
    """Taxa de acerto de cada pergunta em cada cenário (média das repetições): onde cada modelo erra."""
    d = df[df.erro.isna()]
    if cenarios:
        d = d[d.cenario.isin(cenarios)]
    return d.pivot_table(index=["tipo", "pergunta_id"], columns="cenario", values="acerto", aggfunc="mean").round(2)


def comparar(df: pd.DataFrame, a: str, b: str, *, n_boot: int = 2000, semente: int = 0) -> dict:
    """A × B pergunta a pergunta (pareado): diferença de acerto com intervalo de 95% por bootstrap,
    e quantas perguntas só um dos dois acerta. Com ~35 perguntas, diferenças pequenas podem ser ruído."""
    d = df[df.erro.isna() & df.cenario.isin([a, b])]
    t = d.pivot_table(index="pergunta_id", columns="cenario", values="acerto", aggfunc="mean").dropna()
    if t.empty or a not in t or b not in t:
        return {"perguntas": 0}
    dif = (t[b] - t[a]).to_numpy()
    rng = np.random.default_rng(semente)
    boot = [rng.choice(dif, len(dif)).mean() for _ in range(n_boot)]
    return {
        "perguntas": len(t), "acerto_A": float(t[a].mean()), "acerto_B": float(t[b].mean()),
        "diferenca_B_menos_A": float(dif.mean()),
        "ic95": (float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))),
        "so_A_acerta": int(((t[a] >= 0.5) & (t[b] < 0.5)).sum()),
        "so_B_acerta": int(((t[b] >= 0.5) & (t[a] < 0.5)).sum()),
    }


def sugerir_melhor(tabela: pd.DataFrame, provedor: str) -> pd.Series | None:
    """Ordem de desempate: acerto, recusa correta, ferramenta certa, menor custo, menor latência."""
    t = tabela[(tabela.provedor == provedor) & (tabela.respostas > 0)]
    if t.empty:
        return None
    return t.sort_values(["acerto", "recusa_correta", "ferramenta_certa", "custo_por_pergunta_usd", "latencia_mediana_s"],
                         ascending=[False, False, False, True, True]).iloc[0]
