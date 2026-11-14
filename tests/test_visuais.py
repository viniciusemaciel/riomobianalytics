"""Fase 4: validação dos visuais e caminho no agente, com modelo falso (sem banco nem API).

Rode da raiz:  python tests/test_visuais.py      (ou: pytest tests/)
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

from webapp.rag import agent, llm, visuais  # noqa: E402


# ------------------------------------------------------------------ validação
def _erro(fn, *a, **k):
    try:
        fn(*a, **k)
    except visuais.VisualInvalido as e:
        return str(e)
    raise AssertionError("deveria ter recusado")


def test_grafico_valido():
    g = visuais.grafico("linha", "Tiroteios a até 500 m", ["jan/25", "fev/25"],
                        [{"nome": "ocorrências", "valores": [3, "2"]}], "ocorrências", "[1]")
    assert g["tipo"] == "grafico" and g["series"][0]["valores"] == [3.0, 2.0] and g["fonte_id"] == "1"


def test_grafico_recusa_tamanho_diferente_e_sem_fonte():
    assert "iguais" in _erro(visuais.grafico, "barra", "t", ["a", "b"], [{"nome": "x", "valores": [1]}], None, "1")
    assert "fonte_id" in _erro(visuais.grafico, "barra", "t", ["a"], [{"nome": "x", "valores": [1]}], None, None)
    assert "não numérico" in _erro(visuais.grafico, "barra", "t", ["a"], [{"nome": "x", "valores": ["alto"]}], None, "1")
    assert "formato" in _erro(visuais.grafico, "pizza", "t", ["a"], [{"nome": "x", "valores": [1]}], None, "1")


def test_tabela_converte_numeros_e_confere_colunas():
    t = visuais.tabela("Paradas", ["Parada", "Índice"], [["A", "87,5"], ["B", 60]], "2")
    assert t["linhas"] == [["A", 87.5], ["B", 60.0]]
    assert "valores" in _erro(visuais.tabela, "t", ["a", "b"], [["só um"]], "2")


def test_ids_do_mapa_sem_duplicata_e_com_destaque():
    ids, d = visuais.ids_do_mapa(["s1", "s2", "s1"], destaque="s9")
    assert ids == ["s9", "s1", "s2"] and d == "s9"


# ------------------------------------------------------------------ agente
class FalsoLLM:
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
        if nome == "dados":
            return {"dados": {"n": [3, 2]}, "fonte": "Neo4j: teste"}
        if nome == "mostrar_grafico":
            spec = visuais.grafico(**args)
            return {"dados": {"ok": True}, "fonte": "", "visual": spec}
        raise ValueError("ferramenta desconhecida")


def _chamada(nome, args=None, i="t1"):
    return llm.Resposta(texto="", chamadas=[llm.ChamadaFerramenta(id=i, nome=nome, argumentos=args or {})],
                        conteudo=[{"type": "tool_use", "id": i, "name": nome, "input": args or {}}])


def _graf(fonte_id):
    return {"formato": "barra", "titulo": "t", "rotulos": ["a", "b"],
            "series": [{"nome": "x", "valores": [3, 2]}], "fonte_id": fonte_id}


def _rodar(respostas):
    return agent.responder("p", system_prompt="s", ferramentas=Ferramentas, modelo_llm=FalsoLLM(respostas), fallback=False)


def test_visual_entra_no_resultado_e_mantem_a_fonte():
    r = _rodar([_chamada("dados"), _chamada("mostrar_grafico", _graf("1"), "t2"),
                llm.Resposta(texto="Resumo sem citar.")])
    assert len(r.visuais) == 1 and r.visuais[0]["fonte_id"] == "1"
    assert [f["id"] for f in r.fontes] == ["1"]
    assert r.como_dict()["visuais"] == r.visuais


def test_visual_com_fonte_inexistente_e_recusado():
    r = _rodar([_chamada("mostrar_grafico", _graf("7")), llm.Resposta(texto="Não consegui.")])
    assert r.visuais == [] and not r.passos[0].ok and "fonte_id" in r.passos[0].resumo


def test_limite_de_visuais():
    seq = [_chamada("dados")] + [_chamada("mostrar_grafico", _graf("1"), f"g{k}")
                                 for k in range(visuais.MAX_VISUAIS_POR_RESPOSTA + 1)]
    r = _rodar(seq + [llm.Resposta(texto="ok")])
    assert len(r.visuais) == visuais.MAX_VISUAIS_POR_RESPOSTA and not r.passos[-1].ok


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
