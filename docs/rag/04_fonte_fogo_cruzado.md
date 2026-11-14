---
id: 04_fonte_fogo_cruzado
titulo: Fonte de dados — Fogo Cruzado (tiroteios)
tipo: interno
origem: CSV data/fogocruzado/fc_api_occurrences_with_victims_2026-08-01T12_38_31.000Z.csv; scripts 08 e 10; notebook 02
url: https://fogocruzado.org.br/
periodo_coberto: 2019-12-31 (21h01, horário local) a 2025-12-31 (14h05)
atualizado_em: 2026-11-14
tags: [Fogo Cruzado, tiroteios, ocorrências, período, Grande Rio, vítimas, ação policial]
---

## O que é a base do Fogo Cruzado no projeto

O Fogo Cruzado é um instituto independente que registra tiroteios na região metropolitana do Rio e em outras regiões, e publica os dados por API. O projeto usa uma exportação dessa API, "ocorrências com vítimas", feita em 01/08/2026 (data no nome do arquivo). A metodologia do instituto está resumida no arquivo 21.

Cada linha é **uma ocorrência de tiroteio** (não uma vítima), com endereço, município, bairro segundo o instituto, latitude, longitude, data e hora local, indicação de ação policial, presença de agente, motivo principal, indicador de chacina e contagens de feridos e mortos por perfil. São 20.633 linhas de 21 municípios, de 31/12/2019 (a partir das 21h01) a 31/12/2025 (até as 14h05). Só 3 linhas caem em dezembro de 2019 (pelo corte em UTC, que o projeto não corrigiu): na prática a base cobre **2020 a 2025**.

## Números por ano (base do projeto)

Grande Rio (todas as linhas): tiroteios, pessoas baleadas (mortos + feridos, civis e agentes) e mortos.

| Ano | Tiroteios | Baleados | Mortos |
|---|---|---|---|
| 2020 | 4.590 | 1.794 | 896 |
| 2021 | 4.645 | 2.092 | 1.079 |
| 2022 | 3.596 | 2.003 | 987 |
| 2023 | 2.947 | 1.844 | 961 |
| 2024 | 2.536 | 1.573 | 766 |
| 2025 | 2.316 | 1.722 | 946 |

Cidade do Rio de Janeiro (12.637 linhas): tiroteios 2.724, 2.503, 2.176, 1.975, 1.690 e 1.567 de 2020 a 2025; baleados 726, 767, 948, 1.003, 867 e 1.066; mortos 314, 391, 453, 531, 408 e 584.

Leitura correta: o número de **tiroteios** cai ano a ano, mas o de **pessoas baleadas** na cidade sobe em 2025. São medidas diferentes (ocorrência × vítima), e o assistente não deve dizer que "a violência diminuiu" só pela primeira.

## Indicadores de chacina e de ação policial na base

A coluna de chacina (`massacre`) está marcada em 294 das 20.633 ocorrências (152 na cidade do Rio). Em 285 delas há três ou mais civis mortos, que é a definição de "chacina" usada pelo Fogo Cruzado (arquivo 21). A coluna de ação policial (`police_action`) está marcada em 6.600 ocorrências (32%), e 207 das 294 chacinas ocorreram em ação policial. São indicadores do instituto: as ferramentas prontas do assistente não os expõem, e ele só pode falar de chacinas como contexto (arquivos 21 e 22).

## A Operação Contenção na base: um único registro com 122 mortes

A operação de 28/10/2025 nos complexos do Alemão e da Penha aparece como **uma única ocorrência** (id 74284), no Complexo da Penha (bairro Penha), às 02h00 do dia 28/10/2025, com **117 civis e 5 agentes mortos** (compatível com o balanço de 121 mortos mais o quinto policial que morreu depois) e 9 civis e 14 agentes feridos. Está marcada como operação policial (PC, Bope, COE, Core e PM) e como chacina. O perfil das vítimas está quase todo zerado: só 7 adolescentes mortos aparecem.

Consequências: (1) esse registro responde por 122 das 584 mortes de 2025 na cidade do Rio (21%) e por 122 das 166 mortes de outubro de 2025 (73%); (2) para tiroteios por parada e por bairro ele vale **uma** ocorrência, num único ponto; (3) o registro tem um único ponto, que não representa a área real da operação; (4) as outras 14 ocorrências de 28 e 29/10 na cidade somam mais 4 mortes (126 nos dois dias). Comparar **mortos** entre anos ou meses exige separar esse registro; comparar **tiroteios** quase não é afetado. O contexto da operação está no arquivo 22.

## Que parte da base entra em cada conta

- **Alvo do modelo**: só linhas com município "Rio de Janeiro" (12.637), contadas por parada e mês, num raio de 500 m.
- **Contagens por parada no grafo (script 10)** e **gráfico mensal do painel da parada**: todas as 20.633 linhas, inclusive de outros municípios. Uma parada perto da divisa pode contar tiroteios de município vizinho, enquanto o alvo do modelo não conta.
- **Contagem por bairro**: usa o bairro oficial (ponto em polígono do Limite de Bairros). Das 12.637 linhas da cidade, 12.633 caem dentro de algum polígono e 4 ficam sem bairro. Veja o arquivo 08.

## O que a base tem e o que o assistente consegue ver

A exportação traz também vítimas por perfil (homens, mulheres, crianças, adolescentes, idosos), agentes feridos e mortos, ação policial, presença de agente e motivo principal. Mas o motivo é "Não identificado" em 55% das ocorrências da cidade, e o campo de motivo complementar vem vazio. **As ferramentas do assistente não expõem vítimas nem motivo**: ele conta ocorrências. Ao ser perguntado sobre vítimas, deve dizer que a base original tem esse detalhe, mas que ele não está disponível nas consultas do app.
