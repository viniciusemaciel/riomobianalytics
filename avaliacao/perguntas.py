"""Bateria de perguntas com resposta conhecida, para medir a busca e o assistente.

Segue o formato dos labs do curso (encontros 5 e 6): cada pergunta diz o que
precisa aparecer no trecho buscado (evidência, para o recall) e na resposta
(chaves, para o acerto), e quais ferramentas o agente deveria usar.

Campos de `Pergunta`:
    id          curto e estável: é a chave dos resultados salvos. Não reaproveite ids.
    texto       a pergunta como o usuário escreveria.
    tipo        "documentacao" | "dados" | "fora" | "vizinho" | "armadilha"
                fora    = fora do escopo; a busca deveria barrar e o agente recusar.
                vizinho = tema próximo ao do projeto que a documentação não cobre
                          (a busca tende a trazer algo; o agente tem de admitir o limite).
    evidencia   textos que o trecho certo contém (todos, sem acento e sem caixa).
                Vazio = a busca não deveria trazer nada. Um item pode ser tupla de alternativas.
    chaves      textos que a resposta certa contém (todos). Item tupla = basta um deles.
    ferramentas pelo menos uma destas tem de aparecer (vazio = nenhuma exigida).
    proibidas   nenhuma destas pode aparecer.
    checks      nomes de verificações de tests/check_armadilhas.py, todas têm de passar.
    contexto    contexto de página (parada selecionada), quando a pergunta precisa.
    nucleo      entra na rodada rápida usada para ajustar parâmetros.

Para revisar o gabarito: no notebook, a célula "Auditar o gabarito" mostra os
5 trechos mais parecidos de cada pergunta.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Ferramentas que leem o banco: não deveriam aparecer em perguntas fora do escopo.
FERRAMENTAS_DE_DADOS = frozenset({
    "estatisticas_gerais", "paradas_mais_criticas", "buscar_parada", "resumo_bairros", "detalhes_parada",
    "reclamacoes_parada", "tiroteios_parada", "tiroteios_bairros", "resumo_reclamacoes", "metricas_linhas",
    "rede_em_volta", "consulta_cypher",
})


@dataclass(frozen=True)
class Pergunta:
    id: str
    texto: str
    tipo: str
    evidencia: tuple = ()
    chaves: tuple = ()
    ferramentas: frozenset = field(default_factory=frozenset)
    proibidas: frozenset = field(default_factory=frozenset)
    checks: tuple = ()
    contexto: dict | None = None
    nucleo: bool = False


def _doc(id, texto, evidencia, chaves, nucleo=False, checks=("respondeu",)):
    return Pergunta(id, texto, "documentacao", tuple(evidencia), tuple(chaves),
                    frozenset({"buscar_conhecimento"}), checks=tuple(checks), nucleo=nucleo)


def _dados(id, texto, ferramentas, chaves=(), nucleo=False):
    return Pergunta(id, texto, "dados", (), tuple(chaves), frozenset(ferramentas),
                    checks=("respondeu", "sem_pct"), nucleo=nucleo)


def _fora(id, texto, nucleo=False):
    return Pergunta(id, texto, "fora", (), (), frozenset(), FERRAMENTAS_DE_DADOS,
                    checks=("respondeu", "recusa_clara", "sem_documentacao_citada"), nucleo=nucleo)


PERGUNTAS: list[Pergunta] = [
    # ------------------------------------------------ documentação (RAG): evidência + resposta
    _doc("doc_indice", "Como o índice de risco de uma parada é calculado?",
         ["parte reativa", "parte preditiva"], [("reclama",), ("tiroteio", "modelo")], nucleo=True),
    _doc("doc_niveis", "Quais são os níveis do índice de risco?",
         ["medio-baixo", "medio-alto"], ["baixo", "medio-baixo", "medio-alto", "alto"], nucleo=True),
    _doc("doc_peso", "Quanto pesa uma reclamação de Segurança Pública no índice?",
         ["1,5", "seguranca publica"], [("1,5", "1.5")], nucleo=True),
    _doc("doc_auc", "Qual é o AUC do modelo de tiroteio?",
         ["0,7105"], [("0,71", "0.71")], nucleo=True),
    _doc("doc_variaveis", "Quantas variáveis o modelo XGBoost usa?",
         ["16 variaveis"], ["16"]),
    _doc("doc_pagerank", "O que o PageRank mede neste projeto?",
         ["pagerank", "central"], [("central", "importan")]),
    _doc("doc_bancos", "Por que o projeto usa Neo4j e MongoDB?",
         ["mongodb guarda"], ["neo4j", "mongodb"], nucleo=True),
    _doc("doc_somar", "Posso somar os tiroteios das paradas para saber o total do bairro?",
         ["varias vezes"], [("varias vezes", "mais de uma vez", "duplic", "mesmo tiroteio", "repet")]),
    # sem a verificação "sem_pct": a pergunta traz "80%" e a resposta certa o repete ao negar
    _doc("doc_probabilidade", "Um índice 80 quer dizer 80% de chance de tiroteio?",
         ["probabilidade"], [("relativ", "compar", "nao e probabilidade", "nao significa")],
         nucleo=True, checks=("respondeu",)),
    _doc("doc_ligacao", "Como uma reclamação do 1746 é ligada a uma parada?",
         ["parada mais proxima"], ["mais proxima"]),
    _doc("doc_santa_cruz", "Por que a região de Santa Cruz não aparece com paradas no app?",
         ["40 km"], [("40 km", "40km", "40 quilometros")], nucleo=True),
    _doc("doc_horario", "Em que horário do dia acontecem mais tiroteios?",
         ["madrugada"], ["madrugada"]),
    _doc("doc_isp", "Quais são os indicadores estratégicos de criminalidade do ISP?",
         ["letalidade violenta"], ["letalidade", "roubo de carga"]),
    _doc("doc_baleados", "Quantas pessoas foram baleadas no transporte público segundo o Fogo Cruzado?",
         ["156"], ["156"], checks=("respondeu", "atribui_ao_externo")),
    # pode responder pela documentação ou lendo a data no banco (consulta_cypher); basta citar a execução ou o período
    Pergunta("doc_data", "A que data se refere o índice de risco das paradas?", "documentacao", ("last_prediction_date",),
             (("2025", "execucao"),), frozenset({"buscar_conhecimento", "consulta_cypher"}), checks=("respondeu",)),

    # ------------------------------------------------ dados ao vivo (Neo4j): ferramenta certa
    _dados("dados_top5", "Quais são as 5 paradas com maior índice de risco?", {"paradas_mais_criticas"}, nucleo=True),
    _dados("dados_niveis", "Quantas paradas o projeto tem em cada nível de risco?", {"estatisticas_gerais", "consulta_cypher"}),
    _dados("dados_bairros", "Quais bairros tiveram mais tiroteios?", {"tiroteios_bairros"}, nucleo=True),
    _dados("dados_linhas", "Quais linhas de ônibus têm o maior risco médio?", {"metricas_linhas"}),
    _dados("dados_ajuda", "O que você consegue responder?", {"o_que_posso_perguntar"}, nucleo=True),

    # ------------------------------------------------ fora do escopo: a busca deve barrar, o agente recusar
    _fora("fora_copa", "Quem ganhou a Copa do Mundo de 2022?", nucleo=True),
    _fora("fora_receita", "Me passa uma receita de feijoada."),
    _fora("fora_tempo", "Vai chover amanhã no Rio de Janeiro?", nucleo=True),
    _fora("fora_dolar", "Quanto está o dólar hoje?"),
]

# ------------------------------------------------ armadilhas: as mesmas de tests/check_armadilhas.py
# (id, número da armadilha, ferramentas exigidas, tipo, entra no núcleo)
_ARMADILHAS = [
    ("arm_pct", 1, (), "armadilha", True),
    ("arm_conselho", 2, (), "armadilha", False),
    ("arm_injecao", 3, (), "armadilha", True),
    ("arm_apagar", 4, (), "armadilha", False),
    ("arm_cypher_escrita", 5, (), "armadilha", False),
    ("arm_cypher_ok", 6, ("consulta_cypher",), "armadilha", False),
    ("arm_orcamento", 7, (), "vizinho", True),
    ("arm_contencao", 8, ("buscar_conhecimento",), "armadilha", True),
    ("arm_faccao", 9, (), "vizinho", True),
    ("arm_isp_numero", 10, (), "vizinho", False),
    ("arm_adpf", 11, ("buscar_conhecimento",), "armadilha", False),
]


def _carregar_armadilhas() -> list[Pergunta]:
    from tests import check_armadilhas as ca

    saida = []
    for id_, n, ferr, tipo, nucleo in _ARMADILHAS:
        _nome, texto, contexto, checks = ca.ARMADILHAS[n - 1]
        trocas = {"admite_limite": "recusa_clara"}   # ver benchmark.recusa_clara
        if id_ == "arm_injecao":
            trocas["sem_pct"] = "injecao_ignorada"   # a resposta certa cita o "0%" ao dizer que ignorou a instrução
        nomes = tuple(trocas.get(c.__name__, c.__name__) for c in checks)
        saida.append(Pergunta(id_, texto, tipo, (), (), frozenset(ferr), checks=nomes,
                              contexto=contexto, nucleo=nucleo))
    return saida


def todas(*, so_nucleo: bool = False, incluir_armadilhas: bool = True) -> list[Pergunta]:
    lista = PERGUNTAS + (_carregar_armadilhas() if incluir_armadilhas else [])
    ids = [p.id for p in lista]
    assert len(ids) == len(set(ids)), "ids repetidos na bateria"
    return [p for p in lista if p.nucleo] if so_nucleo else lista


def para_busca() -> list[Pergunta]:
    """Perguntas que entram no teste da busca: documentação (tem evidência) e fora do escopo (não pode trazer nada).
    'vizinho' entra à parte, porque o esperado ali é o agente admitir o limite, não a busca barrar."""
    return [p for p in todas() if p.tipo in ("documentacao", "fora", "vizinho")]
