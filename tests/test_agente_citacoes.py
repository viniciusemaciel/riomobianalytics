"""Teste do agente com modelo falso: citação [n] sem fonte é removida; com fonte, fica.

Rode da raiz:  python tests/test_agente_citacoes.py      (ou: pytest tests/)
"""
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

cfg = types.ModuleType("config")
for k, v in dict(RAG_MAX_RODADAS=6, RAG_MAX_HISTORICO=10, RAG_FALLBACK=False, ANTHROPIC_API_KEY="", GEMINI_API_KEY="",
                 RAG_MODEL="m", RAG_MODEL_GEMINI="g", RAG_PROVEDOR_PADRAO="anthropic",
                 RAG_PRECO_ENTRADA_MTOK=0, RAG_PRECO_SAIDA_MTOK=0, RAG_PRECO_GEMINI_ENTRADA_MTOK=0,
                 RAG_PRECO_GEMINI_SAIDA_MTOK=0).items():
    setattr(cfg, k, v)
sys.modules.setdefault("config", cfg)

from webapp.rag import agent, llm  # noqa: E402


class FalsoLLM:
    """Responde com a sequência dada; PROVEDORES etc. imitam o módulo llm."""
    ErroLLM = llm.ErroLLM
    PROVEDORES = {"anthropic": types.SimpleNamespace(nome="Falso")}

    def __init__(self, respostas):
        self.respostas = list(respostas)

    def provedor_padrao(self):
        return "anthropic"

    def alternativo(self, _):
        return None

    def chamar(self, *a, **k):
        return self.respostas.pop(0)


class Ferramentas:
    DEFINICOES = []

    @staticmethod
    def executar(nome, args):
        if nome == "erra":
            raise ValueError("parada X não encontrada")
        return {"dados": {"n": 1}, "fonte": "Neo4j: teste"}


def _rodar(respostas):
    return agent.responder("p", system_prompt="s", ferramentas=Ferramentas, modelo_llm=FalsoLLM(respostas), fallback=False)


def _chamada(nome):
    return llm.Resposta(texto="", chamadas=[llm.ChamadaFerramenta(id="t1", nome=nome, argumentos={})],
                        conteudo=[{"type": "tool_use", "id": "t1", "name": nome, "input": {}}])


def test_citacao_sem_fonte_e_removida():
    # a ferramenta deu erro: nenhuma fonte existe, então o [1] do modelo não pode ficar
    r = _rodar([_chamada("erra"), llm.Resposta(texto="A parada não foi encontrada [1]. Tente outro nome.")])
    assert "[1]" not in r.texto and r.texto.startswith("A parada não foi encontrada.")
    assert r.fontes == []


def test_citacao_com_fonte_fica():
    r = _rodar([_chamada("ok"), llm.Resposta(texto="Há 1 parada [1]. Isso é só método [2].")])
    assert "[1]" in r.texto and "[2]" not in r.texto
    assert [f["id"] for f in r.fontes] == ["1"]


def test_sem_ferramenta_nenhuma_citacao():
    r = _rodar([llm.Resposta(texto="Não dou conselho pessoal [1].")])
    assert r.texto == "Não dou conselho pessoal."


if __name__ == "__main__":
    falhas = 0
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok    {nome}")
            except AssertionError as e:
                falhas += 1
                print(f"FALHA {nome}: {e}")
    sys.exit(1 if falhas else 0)
