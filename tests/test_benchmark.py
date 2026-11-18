"""Testa o benchmark (avaliacao/) sem API: embedding, modelo e ferramentas falsos.

Rode da raiz:  python tests/test_benchmark.py
"""
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from avaliacao import benchmark as bm, perguntas as bateria  # noqa: E402
from webapp.rag import conhecimento, llm  # noqa: E402

REAL = config.ARTIFACTS_DIR / "benchmark"
CENARIOS_DO_TESTE = {"claude · t", "gemini · t", "claude · rpm", "gemini · 429", "gemini · 5xx", "gemini · 503", "gemini · rede", "gemini · orcamento"}


def _cenarios_reais():
    import json
    arq = REAL / "respostas.jsonl"
    if not arq.exists():
        return set()
    return {json.loads(l)["cenario"] for l in arq.read_text(encoding="utf-8").splitlines() if l.strip()}


TMP = Path(tempfile.mkdtemp())
bm.SAIDA = TMP
bm.ESPERAS_LIMITE = (0.01, 0.01)
bm.ESPERAS_INDISPONIVEL = (0.01, 0.01)
bm.ESPERAS_SEM_REDE = (0.01, 0.01)
bm.ARQ_EMB, bm.ARQ_BUSCA, bm.ARQ_BUSCA_DETALHE, bm.ARQ_RESPOSTAS = (TMP / "e.npz", TMP / "b.csv", TMP / "bd.csv", TMP / "r.jsonl")
bm.ARQ_INCIDENTES, bm.ARQ_SONDA = TMP / "inc.jsonl", TMP / "sonda.jsonl"

indice = conhecimento.carregar_indice()
textos = [bm.sem_acento(f"{c['titulo']} {c['secao']} {c['texto']}") for c in indice.chunks]
rng = np.random.default_rng(0)
chamadas_emb = []


def embutidor(lista, tarefa):
    """Pergunta coberta -> vetor perto do trecho com a evidência (cos ~0,8); fora -> aleatório (cos ~0)."""
    chamadas_emb.append(len(lista))
    por_texto = {p.texto: p for p in bateria.todas()}
    out = []
    for t in lista:
        p = por_texto[t]
        alvo = next((i for i, x in enumerate(textos) if p.evidencia and all(bm.contem(x, e) for e in p.evidencia)), None)
        ruido = rng.normal(size=indice.vetores.shape[1])
        ruido /= np.linalg.norm(ruido)
        v = 0.8 * indice.vetores[alvo] + 0.6 * ruido if alvo is not None else ruido
        out.append(v / np.linalg.norm(v))
    return np.array(out, dtype=np.float32)


# ---------------------------------------------------------------- busca
grade, det = bm.avaliar_busca(ks=[1, 2], limiares=[0.3, 0.6, 0.9], indice=indice, embutidor=embutidor)
assert set(grade.columns) >= {"recall@k", "mrr@k", "fora_bloqueadas", "falsos_bloqueios"}
assert det[det.tipo == "documentacao"].pos_evidencia.notna().all(), det[det.pos_evidencia.isna()]
g = grade.set_index(["top_k", "limiar"])
assert g.loc[(2, 0.3), "fora_bloqueadas"] == 1.0, g          # aleatório fica abaixo de 0,3
assert g.loc[(2, 0.9), "falsos_bloqueios"] == 1.0, g          # 0,8 não passa de 0,9
bm.avaliar_busca(ks=[1], limiares=[0.5], indice=indice, embutidor=embutidor)
assert len(chamadas_emb) == 1, "o cache de embeddings não foi usado"
print("busca ok:", g.loc[(2, 0.6)][["recall@k", "mrr@k", "fora_bloqueadas"]].to_dict())


# ---------------------------------------------------------------- respostas
vistos = []


class FakeLLM:
    PROVEDORES = llm.PROVEDORES
    cota_gemini = 3
    falhas_passageiras = 0
    msg_passageira = "cota do Gemini esgotada"

    @staticmethod
    def provedor_padrao():
        return "anthropic"

    @staticmethod
    def alternativo(p):
        return None

    @classmethod
    def chamar(cls, system, mensagens, ferramentas, *, provedor=None, permitir_ferramentas=True, max_tokens=1200):
        vistos.append((provedor, config.RAG_TEMPERATURA, config.RAG_MAX_RODADAS, config.RAG_GEMINI_THINKING))
        if provedor == "gemini" and cls.falhas_passageiras:
            cls.falhas_passageiras -= 1
            raise llm.ErroLLM(cls.msg_passageira)
        if provedor == "gemini":
            cls.cota_gemini -= 1
            if cls.cota_gemini < 0:
                raise llm.ErroLLM("cota do Gemini esgotada")
        uso = {"entrada": 1000, "saida": 100, "cache_leitura": 500, "cache_escrita": 0}
        ultima = mensagens[-1]["content"]
        if isinstance(ultima, str):  # 1ª rodada: pede a documentação
            return llm.Resposta("", [llm.ChamadaFerramenta("t1", "buscar_conhecimento", {"pergunta": ultima})],
                                "tool_use", [{"type": "tool_use", "id": "t1", "name": "buscar_conhecimento", "input": {"pergunta": ultima}}], uso)
        return llm.Resposta("Não tenho isso. O índice é relativo, 16 variáveis [1].", [], "end_turn",
                            [{"type": "text", "text": "x"}], uso)


fake_tools = SimpleNamespace(
    DEFINICOES=[],
    executar=lambda nome, args: {"dados": {"trechos": []}, "fonte": "Documentação do projeto: X > Y"},
)

lista = bateria.todas(so_nucleo=True)[:4]
cfg = bm.Config("anthropic", temperatura=0.0, max_rodadas=3)
df = bm.rodar_cenario("claude · t", cfg, lista, repeticoes=2, modelo_llm=FakeLLM, ferramentas=fake_tools, mostrar=False)
assert len(df) == 8 and df.erro.isna().all()
assert all(v[1] == 0.0 and v[2] == 3 for v in vistos), "parâmetros não aplicados durante a chamada"
assert config.RAG_TEMPERATURA is None and config.RAG_MAX_RODADAS == 6, "parâmetros não restaurados"
assert (df.ferramentas.apply(lambda f: f == ["buscar_conhecimento"])).all()
assert df.custo_usd.gt(0).all()

# retomada: nada a refazer
n = len(vistos)
bm.rodar_cenario("claude · t", cfg, lista, repeticoes=2, modelo_llm=FakeLLM, ferramentas=fake_tools, mostrar=False)
assert len(vistos) == n, "retomada refez perguntas já gravadas"

# mesmo nome com outros parâmetros: recusa
try:
    bm.rodar_cenario("claude · t", cfg.mudar(top_k=3), lista, modelo_llm=FakeLLM, ferramentas=fake_tools, mostrar=False)
    raise AssertionError("aceitou parâmetros diferentes no mesmo cenário")
except ValueError:
    pass

# limite por minuto: com RPM 3 numa janela de 0,3 s, 6 chamadas levam pelo menos 0,3 s
import time  # noqa: E402
bm.RPM["anthropic"], bm.JANELA_S = 3, 0.3
t0 = time.monotonic()
bm.rodar_cenario("claude · rpm", cfg, lista[:3], modelo_llm=FakeLLM, ferramentas=fake_tools, mostrar=False)
assert time.monotonic() - t0 >= 0.3, "o limitador não segurou as chamadas"
bm.RPM["anthropic"] = None
bm.apagar_cenario("claude · rpm")

# 429 passageiro: espera, tenta de novo e a pergunta sai sem erro
FakeLLM.falhas_passageiras = 2
d0 = bm.rodar_cenario("gemini · 429", bm.Config("gemini"), lista[:1], pausa_s=0, modelo_llm=FakeLLM, ferramentas=fake_tools, mostrar=False)
assert d0.erro.isna().all() and FakeLLM.falhas_passageiras == 0, d0[["pergunta_id", "erro"]]
bm.apagar_cenario("gemini · 429")

# 503 e queda de internet: mesma coisa, a pergunta sai sem erro
FakeLLM.cota_gemini = 10**6
for msg in ("o Gemini devolveu erro 503", "sem conexão com o Gemini"):
    FakeLLM.msg_passageira, FakeLLM.falhas_passageiras = msg, 2
    d0 = bm.rodar_cenario("gemini · 5xx", bm.Config("gemini"), lista[:1], pausa_s=0, modelo_llm=FakeLLM, ferramentas=fake_tools, mostrar=False)
    assert d0.erro.isna().all() and FakeLLM.falhas_passageiras == 0, (msg, d0[["pergunta_id", "erro"]])
    bm.apagar_cenario("gemini · 5xx")
# 503 que não passa: grava o erro e SEGUE (não para a rodada); sem rede que não volta: PARA
FakeLLM.msg_passageira, FakeLLM.falhas_passageiras = "o Gemini devolveu erro 503", 10**6
d0 = bm.rodar_cenario("gemini · 503", bm.Config("gemini"), lista[:3], pausa_s=0, modelo_llm=FakeLLM, ferramentas=fake_tools, mostrar=False)
assert len(d0) == 3 and d0.erro.notna().all(), d0[["pergunta_id", "erro"]]
bm.apagar_cenario("gemini · 503")
FakeLLM.msg_passageira = "sem conexão com o Gemini"
d0 = bm.rodar_cenario("gemini · rede", bm.Config("gemini"), lista[:3], pausa_s=0, modelo_llm=FakeLLM, ferramentas=fake_tools, mostrar=False)
assert len(d0) == 1, "deveria parar na primeira pergunta sem rede"
bm.apagar_cenario("gemini · rede")
FakeLLM.msg_passageira, FakeLLM.falhas_passageiras = "cota do Gemini esgotada", 0

# incidentes: as falhas acima ficaram registradas, com desfecho e código
inc = bm.carregar_incidentes()
assert {"recuperou", "desistiu"} <= set(inc.desfecho), inc.desfecho.value_counts()
assert 503 in set(bm.resumo_incidentes(inc).codigo), bm.resumo_incidentes(inc)
assert inc.cenario.notna().all() and inc.rodada.ge(1).all()

# orçamento do dia: para antes de passar do teto e retoma depois
bm.ORCAMENTO_DIA["gemini"] = bm.chamadas_hoje("gemini") + 1
d0 = bm.rodar_cenario("gemini · orcamento", bm.Config("gemini"), lista, pausa_s=0, modelo_llm=FakeLLM, ferramentas=fake_tools, mostrar=False)
assert 1 <= len(d0) < len(lista), len(d0)
est = bm.estimar("gemini · orcamento", bm.Config("gemini"), lista)
assert est["respostas_faltando"] == len(lista) - len(d0) and est["chamadas_estimadas"] > 0, est
bm.ORCAMENTO_DIA["gemini"] = None
d0 = bm.rodar_cenario("gemini · orcamento", bm.Config("gemini"), lista, pausa_s=0, modelo_llm=FakeLLM, ferramentas=fake_tools, mostrar=False)
assert len(d0) == len(lista)
bm.apagar_cenario("gemini · orcamento")

# cota do dia: depois das novas tentativas, para no erro e retoma depois
FakeLLM.cota_gemini = 3
gcfg = bm.Config("gemini", thinking="minimal")
d1 = bm.rodar_cenario("gemini · t", gcfg, lista, pausa_s=0, modelo_llm=FakeLLM, ferramentas=fake_tools, mostrar=False)
assert d1.erro.notna().sum() == 1 and len(d1) == 2, d1[["pergunta_id", "erro"]]
FakeLLM.cota_gemini = 100
d2 = bm.rodar_cenario("gemini · t", gcfg, lista, pausa_s=0, modelo_llm=FakeLLM, ferramentas=fake_tools, mostrar=False)
assert len(d2) == 4 and d2.erro.isna().all(), d2[["pergunta_id", "erro"]]
assert any(v[0] == "gemini" and v[3] == "minimal" for v in vistos)

todas = bm.carregar_respostas()
r = bm.resumo(todas)
assert set(r.cenario) == {"claude · t", "gemini · t"}
assert r.set_index("cenario").loc["claude · t", "consistencia_veredito"] == 1.0
c = bm.comparar(todas, "claude · t", "gemini · t")
assert c["perguntas"] == 4, c
assert not bm.por_pergunta(todas).empty
assert bm.sugerir_melhor(r, "gemini").cenario == "gemini · t"
assert bm.apagar_cenario("gemini · t") == 5 and set(bm.carregar_respostas().cenario) == {"claude · t"}
print("respostas ok:", r[["cenario", "respostas", "acerto", "recusa_correta", "ferramenta_certa", "custo_10mil_usd"]].to_dict("records"))
assert not (_cenarios_reais() & CENARIOS_DO_TESTE), "o teste gravou cenários falsos em artifacts/benchmark"
print("Tudo certo.")
