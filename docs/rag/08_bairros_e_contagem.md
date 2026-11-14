---
id: 08_bairros_e_contagem
titulo: Bairro oficial e as duas regras de contagem de tiroteios
tipo: interno
origem: scripts 08, 09 e 10; webapp/rag/prompts.py
url: https://github.com/viniciusemaciel/riomobianalytics
periodo_coberto: tiroteios 2020–2025
atualizado_em: 2026-11-14
tags: [bairro oficial, exposição, ocorrência, contagem, tiroteios_500m, ponto em polígono]
---

## Bairro oficial: de onde vem

O bairro de uma parada ou de um tiroteio vem do arquivo **Limite de Bairros** da Prefeitura do Rio (164 polígonos). O projeto faz um "ponto em polígono": a coordenada cai dentro de qual bairro? Isso é feito para as paradas (script 09, gravando `Stop.bairro`) e para os tiroteios (script 08). Não se usa o bairro que o Fogo Cruzado informa nem o que o 1746 traz, para ter uma única régua oficial; por isso os nomes podem diferir dos da fonte original.

Das 12.637 ocorrências do município do Rio, 12.633 caem dentro de algum polígono; 4 ficam sem bairro. Ocorrências de outros municípios não têm bairro oficial.

## Duas regras de contagem, para duas perguntas

**Parada = exposição.** `tiroteios_500m_total` e `tiroteios_500m_12m` contam as ocorrências a até 500 m da parada (mesmo raio do alvo do modelo). Um tiroteio **conta para todas as paradas dentro do raio**, de propósito: a pergunta é "a quantos tiroteios esta parada esteve exposta?".

**Bairro = ocorrência.** Cada tiroteio é contado **uma única vez**, no bairro oficial onde ocorreu. A pergunta é "quantos tiroteios aconteceram neste bairro?".

## Por que não se pode somar paradas para obter o bairro

Somar a exposição de todas as paradas de um bairro conta o mesmo tiroteio várias vezes (uma vez por parada que estava a menos de 500 m dele) e pode dar um total maior que o do próprio bairro. Por isso o assistente tem ferramentas separadas: `tiroteios_parada` (exposição) e `tiroteios_bairros` (ocorrência). A regra do assistente é nunca somar paradas para responder por bairro e nunca comparar os dois tipos de número como se fossem a mesma coisa.

## O que cada conta inclui

- As contagens por parada e o gráfico mensal do painel da parada usam todas as 20.633 ocorrências da base, inclusive de municípios vizinhos; paradas perto da divisa podem somar tiroteios de fora da cidade.
- O alvo do modelo usa só as 12.637 do município do Rio.
- O mesmo tiroteio, portanto, pode aparecer em totais diferentes dependendo da pergunta, e isso é esperado.

## Como falar de bairro com cuidado

Um número alto de tiroteios num bairro descreve **o registro de ocorrências**, não a população nem o comportamento de quem mora lá. Bairros grandes, com mais ruas e mais gente, tendem a ter mais ocorrências. O projeto não calcula taxa por habitante. Para situar um bairro na sua região (área e região de planejamento), veja o arquivo 15. O assistente deve citar o período dos dados e evitar rótulos como "perigoso" ou "violento" para bairros.
