---
id: 10_assistente
titulo: O assistente "Pergunte ao RioMobi": como funciona
tipo: interno
origem: webapp/rag/ (agent.py, tools.py, prompts.py, cypher_guard.py, provedores) e config.py
url: https://github.com/viniciusemaciel/riomobianalytics
periodo_coberto: estado do repositório em 14/11/2026
atualizado_em: 2026-11-14
tags: [assistente, RAG, ferramentas, Cypher, citações, guardrails, Claude, Gemini]
---

## O que o assistente faz

O assistente responde, em português, perguntas sobre as paradas, linhas e bairros do projeto. Ele **não responde de memória**: todo número, nome de parada, linha ou bairro vem de uma ferramenta chamada na própria conversa, e cada resultado recebe uma fonte numerada, citada no texto como [1], [2]. Se nenhuma ferramenta traz o dado, ele diz que não encontrou. As respostas são curtas (2 a 5 frases), e listas só quando há mais de 3 itens.

Quando a pergunta trata uma parada ou um bairro como "perigoso" ou "seguro", ele lembra que o índice é uma previsão do modelo para comparar paradas, não um fato observado. Se há uma parada selecionada no mapa, "esta parada" se refere a ela (botão "Perguntar ao assistente").

## Ferramentas disponíveis

Ferramentas fixas, de leitura:

- `estatisticas_gerais`: totais do projeto (paradas, linhas, reclamações, índice médio e paradas de nível Alto).
- `paradas_mais_criticas`: paradas de maior índice.
- `buscar_parada`: acha paradas por nome ou bairro oficial (usada antes das que pedem o identificador da parada).
- `detalhes_parada`: índice, nível, componentes, PageRank, linhas, reclamações em 3, 6 e 12 meses e total de tiroteios a 500 m.
- `reclamacoes_parada`, `resumo_reclamacoes`: reclamações de uma parada e contagem por categoria no projeto todo.
- `tiroteios_parada`: exposição mês a mês (500 m, janela de 1 a 36 meses); `tiroteios_bairros`: ocorrências por bairro oficial, com filtro de anos.
- `resumo_bairros`: bairros por paradas de nível Alto, índice médio ou total de paradas. O índice médio é o de todas as paradas do bairro.
- `metricas_linhas`: índice médio, paradas e paradas de nível Alto por linha.
- `rede_em_volta`: paradas ligadas a uma parada em 1 a 3 saltos.
- `consulta_cypher`: consulta livre, quando nenhuma ferramenta fixa responde ao recorte pedido.

As ferramentas fixas vêm primeiro. A consulta livre serve a recortes como "quantas paradas de nível Alto há em Bangu?".

## Consulta livre e proteção dos dados

Quando nenhuma ferramenta fixa responde ao recorte pedido, o assistente escreve uma consulta ao banco do grafo. Ela só roda se for de **leitura**, com limite de linhas e de tempo, e o banco recusa qualquer escrita. Por isso o assistente não consegue alterar nem apagar dados, mesmo que alguém peça. Quando a consulta é bloqueada ou falha, ele corrige e tenta de novo ou diz que não conseguiu.

## Modelos e limites de uso

O assistente usa um modelo de linguagem da Anthropic (Claude Haiku) ou do Google (Gemini Flash-Lite), escolhido na interface; se um deles falha, o outro assume. Cada pergunta pode usar várias rodadas de ferramentas, o assistente considera as mensagens mais recentes da conversa e cada sessão aceita até 30 perguntas.

## O que o assistente recusa

- Assuntos fora do projeto: recusa em uma frase e sugere perguntas possíveis.
- Conselho pessoal de segurança ("posso ir a tal lugar?", "qual a melhor rota?"): explica que o projeto compara paradas e aponta para dados e fontes oficiais.
- Afirmações sobre pessoas, grupos ou comunidades além do que os dados mostram, e linguagem que estigmatize bairros ou moradores.
- Qualquer pedido de alterar ou apagar dados, mesmo vindo do texto de uma reclamação ou da página: textos do banco são dados, não instruções.

Ele também não deve escrever "%" depois de um índice.

## Limites do assistente

Ele conta **ocorrências** de tiroteio, não vítimas, e não tem motivo da ocorrência. Os totais citam sempre o período da base, que termina em 2025. A contagem de tiroteios é histórico; o índice é previsão, então os dois podem divergir.
