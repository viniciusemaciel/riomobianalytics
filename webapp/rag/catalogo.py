"""O que o assistente sabe e o que dá para perguntar.

Fonte única para três lugares: o seletor de temas da página do Assistente, o
painel "O que o assistente sabe" e a ferramenta `o_que_posso_perguntar` (quando
o usuário pergunta no chat "o que você sabe fazer?"). Não depende do Streamlit
nem de banco, e não chama nenhum modelo.

Cada pergunta de exemplo de documentação traz os arquivos de docs/rag em que a
resposta deve estar (`docs`). `tests/check_catalogo.py` confere, com o índice
real, que a busca encontra um deles; assim nenhum botão leva a "não encontrei".
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Pergunta:
    texto: str
    docs: tuple[str, ...] = ()    # ids de docs/rag que devem responder (vazio = responde com dados ao vivo)


@dataclass(frozen=True)
class Tema:
    id: str
    nome: str                     # rótulo curto do seletor
    descricao: str                # uma frase: o que há aqui
    perguntas: tuple[Pergunta, ...] = field(default_factory=tuple)


TEMA_PARADA = Tema(
    "parada", "Esta parada",
    "Índice, tiroteios por perto, linhas e paradas vizinhas da parada selecionada.",
    (Pergunta("Por que esta parada tem esse índice de risco?"),
     Pergunta("Mostre os tiroteios perto desta parada mês a mês"),
     Pergunta("Mostre no mapa as paradas vizinhas e o índice de cada uma")),
)

TEMAS = (
    Tema("dados", "Paradas e bairros",
         "Índice de risco, reclamações do 1746 e tiroteios por parada, bairro e linha, direto do banco.",
         (Pergunta("Mostre no mapa as 10 paradas com maior índice de risco"),
          Pergunta("Quais bairros têm mais paradas de nível alto? Mostre num gráfico"),
          Pergunta("Quais bairros tiveram mais tiroteios em 2025?"))),
    Tema("metodo", "O índice",
         "O cálculo do índice, o modelo, o que cada nível quer dizer e os limites da leitura.",
         (Pergunta("Como o índice de risco é calculado?", ("05_metodologia_risco", "12_glossario", "13_faq")),
          Pergunta("O que significa uma parada de nível Alto?", ("05_metodologia_risco", "12_glossario", "13_faq", "11_uso_responsavel")),
          Pergunta("Quão confiável é o modelo?", ("06_modelo", "13_faq", "11_uso_responsavel")))),
    Tema("contexto", "Segurança no Rio",
         "Resumos de fontes públicas de 2019 a 2025, sempre com a fonte. Não são dados do projeto.",
         (Pergunta("O que foi a Operação Contenção e como ela aparece nos dados?",
                   ("22_contexto_linha_do_tempo_2019_2025", "04_fonte_fogo_cruzado", "13_faq")),
          Pergunta("O que é a ADPF 635?", ("22_contexto_linha_do_tempo_2019_2025", "13_faq", "12_glossario")),
          Pergunta("Qual a diferença entre os números do ISP e os do Fogo Cruzado?",
                   ("20_contexto_isp", "21_contexto_fogo_cruzado_relatorios", "13_faq")))),
    Tema("uso", "Dados e app",
         "De onde vêm os dados, o período que cobrem e como ler o mapa e a rede.",
         (Pergunta("De onde vêm os dados e até quando eles vão?",
                   ("09_arquitetura", "13_faq", "01_projeto", "02_fonte_gtfs", "03_fonte_1746", "04_fonte_fogo_cruzado")),
          Pergunta("Por que somar as paradas não dá o total de tiroteios do bairro?",
                   ("08_bairros_e_contagem", "13_faq")),
          Pergunta("Como eu uso o mapa?", ("14_guia_do_app", "01_projeto")))),
)

# Dados que as ferramentas consultam ao vivo (os períodos são os das bases carregadas).
DADOS_AO_VIVO = (
    ("Paradas e linhas de ônibus", "GTFS: 6.426 paradas e 510 linhas"),
    ("Índice de risco", "0 a 100 por parada, com quatro níveis; compara paradas, não é probabilidade"),
    ("Reclamações", "Central 1746, ligadas às paradas próximas, até dez/2025"),
    ("Tiroteios", "Fogo Cruzado, dez/2019 a dez/2025; conta ocorrências, não vítimas"),
)

NAO_RESPONDE = (
    "Qual facção ou grupo armado atua num bairro",
    "Números de crimes do ISP (o projeto não usa essa base)",
    "Vítimas e motivo de cada tiroteio",
    "Se é seguro ir a um lugar ou qual rota pegar",
    "Previsão de uma ocorrência específica",
)


def temas(com_parada: bool = False) -> tuple[Tema, ...]:
    return (TEMA_PARADA, *TEMAS) if com_parada else TEMAS


def documentos(chunks: list[dict] | None = None) -> list[dict]:
    """Um item por arquivo da documentação: titulo, tipo, periodo_coberto, acessado_em, secoes.

    Lê os chunks do índice (artifacts/rag_index) e, sem índice, os próprios arquivos de docs/rag.
    """
    if chunks is None:
        from . import conhecimento
        try:
            chunks = conhecimento.carregar_indice().chunks
        except Exception:
            chunks = conhecimento.montar_chunks()
    docs: dict[str, dict] = {}
    for c in chunks:
        d = docs.setdefault(c["arquivo"], {
            "id": c["arquivo"].removesuffix(".md"), "titulo": c["titulo"], "tipo": c.get("tipo", "interno"),
            "periodo_coberto": c.get("periodo_coberto", ""), "acessado_em": c.get("acessado_em", ""), "secoes": 0})
        d["secoes"] += 1
    return [docs[k] for k in sorted(docs)]


def titulo_curto(titulo: str) -> str:
    """'Contexto externo — linha do tempo...' -> 'Linha do tempo...'; 'Fonte de dados — GTFS...' -> 'GTFS...'."""
    if " — " in titulo:
        cabeca, resto = titulo.split(" — ", 1)
        if cabeca.lower() in ("contexto externo", "fonte de dados"):
            return resto[:1].upper() + resto[1:]
    return titulo


def como_dict(com_parada: bool = False) -> dict:
    """Formato devolvido pela ferramenta o_que_posso_perguntar."""
    docs = documentos()
    return {
        "temas": [{"tema": t.nome, "o_que_tem": t.descricao, "exemplos": [p.texto for p in t.perguntas]}
                  for t in temas(com_parada)],
        "dados_ao_vivo": [f"{a}: {b}" for a, b in DADOS_AO_VIVO],
        "documentacao": {
            "do_projeto": [titulo_curto(d["titulo"]) for d in docs if d["tipo"] != "externo"],
            "fontes_externas": [f"{titulo_curto(d['titulo'])} ({d['periodo_coberto']})" for d in docs if d["tipo"] == "externo"],
        },
        "nao_responde": list(NAO_RESPONDE),
    }
