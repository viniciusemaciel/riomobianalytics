"""Guarda das consultas Cypher livres do assistente (ferramenta `consulta_cypher`).

O modelo escreve o Cypher; este módulo decide se ele pode rodar. São três camadas,
de fora para dentro:

  1. este guard (texto): só leitura, uma instrução só, rótulos e relações da lista
     branca, caminhos curtos, sem procedimentos (CALL) nem funções de extensão
     (apoc.*), LIMIT obrigatório de no máximo 50 linhas;
  2. a sessão Neo4j em modo de leitura (`somente_leitura()`): mesmo que algo passe
     pelo guard, o banco recusa escrita;
  3. o timeout da transação (TIMEOUT_S): consulta pesada é cancelada pelo banco.

As mensagens de erro são escritas para o modelo: dizem o que mudar para a consulta
passar. O agente as devolve como resultado de ferramenta com erro.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

LIMITE_PADRAO = 50      # LIMIT acrescentado quando a consulta não tem
LIMITE_MAXIMO = 50      # LIMIT maior que isso é reduzido
MAX_CARACTERES = 1500
MAX_SALTOS = 3          # teto de caminhos de tamanho variável (*1..3)
TIMEOUT_S = 45          # segundos; aplicado pelo Neo4j na transação

# Só o que o assistente precisa. Trip e HAS_STOP ficam de fora (são os horários do
# GTFS, enormes e lentos); Neighborhood também (6 bairros de teste, desatualizados;
# o bairro oficial está em Stop.bairro). Tiroteio vem do scripts/10 (sem relações).
ROTULOS = {"Stop", "Route", "Reclamacao", "Categoria", "Tiroteio"}
RELACOES = {"SERVES", "CONNECTS_TO", "AFFECTS", "HAS_TYPE"}

# Palavras que escrevem, administram ou saem do banco. Comparação sem diferenciar
# maiúsculas e só como palavra inteira (por isso "Stop" e "offset" não colidem).
PROIBIDAS = (
    "CREATE", "MERGE", "DELETE", "DETACH", "SET", "REMOVE", "DROP", "LOAD", "FOREACH",
    "CALL", "USE", "GRANT", "DENY", "REVOKE", "ALTER", "RENAME", "SHOW", "TERMINATE",
    "UNION", "EXPLAIN", "PROFILE", "FINISH", "INSERT",
)
_RE_PROIBIDAS = re.compile(r"\b(" + "|".join(PROIBIDAS) + r")\b", re.IGNORECASE)

# Funções com ponto permitidas (as nativas de espaço e tempo). Todo o resto com ponto
# antes de "(" é extensão (apoc.*, gds.*, db.*, dbms.*) e fica bloqueado.
FUNCOES_COM_PONTO = {
    "point.distance", "point.withinbbox", "date.truncate", "datetime.truncate",
    "localdatetime.truncate", "duration.between", "duration.indays", "duration.inmonths",
    "duration.inseconds", "date.statement", "datetime.statement",
}
_LITERAIS = {"TRUE", "FALSE", "NULL"}
_INICIOS = ("MATCH", "OPTIONAL", "WITH", "UNWIND", "RETURN")


class CypherBloqueado(ValueError):
    """A consulta não passou no guard. A mensagem é dirigida ao modelo."""


@dataclass
class Validada:
    consulta: str                         # texto que vai ao banco (com o LIMIT final)
    limite: int                           # LIMIT efetivo
    avisos: list[str] = field(default_factory=list)


# ------------------------------------------------------------------- utilitários
def _separar(q: str) -> tuple[str, str]:
    """Devolve (texto sem comentários, código sem comentários e com strings vazias).

    O primeiro é o que vai ao banco. O segundo é o que as regras olham: 'CREATE'
    dentro de uma string de busca não é escrita, e um comentário não pode esconder
    nada. Crase (`) é recusada antes.
    """
    saida, limpo, i, n = [], [], 0, len(q)
    while i < n:
        c = q[i]
        if c in "'\"":
            fim = i + 1
            while fim < n and q[fim] != c:
                fim += 2 if q[fim] == "\\" else 1
            if fim >= n:
                raise CypherBloqueado("há uma string sem fechar (aspas). Corrija a consulta.")
            saida.append(c + c)
            limpo.append(q[i:fim + 1])
            i = fim + 1
        elif q.startswith("//", i):
            fim = q.find("\n", i)
            i = n if fim == -1 else fim
        elif q.startswith("/*", i):
            fim = q.find("*/", i + 2)
            if fim == -1:
                raise CypherBloqueado("há um comentário /* sem fechar. Corrija a consulta.")
            saida.append(" ")
            limpo.append(" ")
            i = fim + 2
        else:
            saida.append(c)
            limpo.append(c)
            i += 1
    return "".join(limpo), "".join(saida)


def _checar_rotulos(codigo: str):
    # 1) identificador logo depois de ":" (não "::"): rótulo de nó, tipo de relação
    #    ou valor de mapa. Valor de mapa em minúscula (s.name, n) é ignorado; função
    #    (COUNT(...)) e literal (TRUE) também.
    for m in re.finditer(r"(?<!:):(?!:)\s*([A-Za-z_]\w*)(\s*\()?", codigo):
        nome, eh_funcao = m.group(1), bool(m.group(2))
        if eh_funcao or nome.upper() in _LITERAIS or not nome[0].isupper():
            continue
        if nome not in ROTULOS | RELACOES:
            raise CypherBloqueado(
                f"rótulo ou relação '{nome}' não é permitido. Use só os nós {sorted(ROTULOS)} "
                f"e as relações {sorted(RELACOES)} do esquema (maiúsculas e minúsculas importam).")
    # 2) alternativas dentro de uma relação: [:SERVES|AFFECTS]
    for m in re.finditer(r"\[\s*[A-Za-z_]?\w*\s*:([^\]\*\{]*)", codigo):
        for nome in re.findall(r"[A-Za-z_]\w*", m.group(1)):
            if nome not in RELACOES:
                raise CypherBloqueado(f"relação '{nome}' não é permitida. Relações: {sorted(RELACOES)}.")


def _checar_caminhos(codigo: str):
    for m in re.finditer(r"\[[^\]]*\]", codigo):
        rel = m.group(0)
        if "*" not in rel:
            continue
        faixa = re.search(r"\*\s*(\d*)\s*(\.\.\s*(\d*))?", rel)
        ini, tem_faixa, fim = faixa.group(1), faixa.group(2), faixa.group(3)
        if tem_faixa:
            teto = int(fim) if fim else None
        else:
            teto = int(ini) if ini else None
        if teto is None or teto > MAX_SALTOS:
            raise CypherBloqueado(
                f"caminho de tamanho variável sem teto ou longo demais em '{rel}'. "
                f"Use no máximo *1..{MAX_SALTOS}.")
    # Quantified path patterns do Cypher 5 (()-->(){1,5}, (...)+) não têm teto fácil de checar.
    if re.search(r"\)\s*\{\s*\d*\s*,\s*\d*\s*\}|\)\s*[+*](?!\s*\d)", codigo):
        raise CypherBloqueado(f"padrões de caminho quantificados não são permitidos; use [:REL*1..{MAX_SALTOS}].")


def _checar_funcoes(codigo: str):
    for m in re.finditer(r"\b([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)\s*\(", codigo):
        nome = m.group(1).lower()
        if nome not in FUNCOES_COM_PONTO:
            raise CypherBloqueado(
                f"a função '{m.group(1)}' não é permitida (extensões e procedimentos estão fora). "
                "Use funções nativas do Cypher (count, avg, sum, collect, toLower, point.distance...).")


def _limite_final(texto: str, codigo: str) -> tuple[str, int, list[str]]:
    """Garante um LIMIT numérico no fim de no máximo LIMITE_MAXIMO."""
    avisos = []
    m = re.search(r"\bLIMIT\s+(\S+)\s*$", codigo, re.IGNORECASE)
    if not m:
        return f"{texto.rstrip()}\nLIMIT {LIMITE_PADRAO}", LIMITE_PADRAO, [f"LIMIT {LIMITE_PADRAO} acrescentado"]
    if not m.group(1).isdigit():
        raise CypherBloqueado("o LIMIT final precisa ser um número inteiro (ex.: LIMIT 20).")
    n = int(m.group(1))
    if n > LIMITE_MAXIMO:
        texto = re.sub(r"\bLIMIT\s+\d+\s*$", f"LIMIT {LIMITE_MAXIMO}", texto.rstrip(), flags=re.IGNORECASE)
        avisos.append(f"LIMIT {n} reduzido para {LIMITE_MAXIMO}")
        n = LIMITE_MAXIMO
    return texto, max(n, 0), avisos


# ---------------------------------------------------------------------- entrada
def validar(consulta: str) -> Validada:
    """Devolve a consulta pronta para rodar ou lança CypherBloqueado."""
    if not isinstance(consulta, str) or not consulta.strip():
        raise CypherBloqueado("a consulta veio vazia.")
    texto = consulta.strip()
    if len(texto) > MAX_CARACTERES:
        raise CypherBloqueado(f"consulta longa demais ({len(texto)} caracteres; máximo {MAX_CARACTERES}). Simplifique.")
    if "`" in texto:
        raise CypherBloqueado("crase (`) não é permitida. Use nomes simples do esquema.")
    if "\x00" in texto:
        raise CypherBloqueado("caractere inválido na consulta.")

    texto, codigo = _separar(texto)
    # um ";" final é tolerado; qualquer outro significa mais de uma instrução
    codigo_sem_fim = codigo.rstrip().rstrip(";")
    if ";" in codigo_sem_fim:
        raise CypherBloqueado("só uma instrução por vez (sem ';' no meio).")
    texto = texto.rstrip().rstrip(";")
    codigo = codigo_sem_fim
    if not codigo.strip():
        raise CypherBloqueado("a consulta só tem comentários.")

    primeira = codigo.strip().split(None, 1)[0].upper()
    if primeira not in _INICIOS:
        raise CypherBloqueado(f"a consulta deve começar com MATCH, OPTIONAL MATCH, WITH, UNWIND ou RETURN (começou com {primeira}).")
    proibida = _RE_PROIBIDAS.search(codigo)
    if proibida:
        raise CypherBloqueado(
            f"'{proibida.group(1).upper()}' não é permitido: o assistente só lê dados, uma consulta por vez, sem procedimentos.")
    if not re.search(r"\bRETURN\b", codigo, re.IGNORECASE):
        raise CypherBloqueado("a consulta precisa de RETURN.")

    _checar_rotulos(codigo)
    _checar_caminhos(codigo)
    _checar_funcoes(codigo)

    # o LIMIT é lido no texto limpo, mas aplicado no texto original
    texto_final, limite, avisos = _limite_final(texto, codigo)
    return Validada(consulta=texto_final, limite=limite, avisos=avisos)
