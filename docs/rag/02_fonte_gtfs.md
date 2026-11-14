---
id: 02_fonte_gtfs
titulo: Fonte de dados — GTFS da rede de ônibus
tipo: interno
origem: arquivos GTFS em data/gtfs/ e notebook 01_filtragem_gtfs_1746
periodo_coberto: feed GTFS usado no projeto (6.426 paradas, 510 linhas)
atualizado_em: 2026-11-14
tags: [GTFS, paradas, linhas, viagens, stops, routes, trips, rede de ônibus]
---

## O que é o GTFS e o que o projeto usa dele

GTFS (General Transit Feed Specification) é um formato aberto para descrever transporte público: um conjunto de arquivos de texto com paradas, linhas, viagens e horários. O projeto usa o feed do ônibus municipal do Rio de Janeiro. Os arquivos usados ficam em `data/gtfs/`: `stops.txt` (paradas), `routes.txt` (linhas), `trips.txt` (viagens) e `stop_times.txt` (a sequência de paradas de cada viagem).

A rede descrita aqui é a do feed usado no projeto. Linhas criadas, extintas ou alteradas depois disso não aparecem.

## Tamanho da rede no projeto

Depois da filtragem descrita no notebook 01, a base tem:

- **6.426 paradas** (coordenadas entre latitude −23,03 e −22,78 e longitude −43,56 e −43,16);
- **510 linhas**, das quais 448 têm tipo 700 (serviço de ônibus), 32 têm tipo 702 (ônibus expresso) e 30 têm tipo 200 (serviço rodoviário/coach), segundo os códigos estendidos do GTFS;
- **510 viagens**, uma viagem representativa por linha;
- **25.086 registros de parada por viagem** (média de 50,3 paradas por viagem).

Uma parada atende em média 3,9 linhas; a mais servida atende 60. Há 801 paradas que não aparecem em nenhuma viagem do feed filtrado: existem como pontos no mapa, mas não têm ligações na rede.

## Como o feed foi filtrado

O notebook 01 aplica três escolhas que afetam o que o app mostra:

1. **Raio de 40 km** em torno da Praça XV (centro do Rio): paradas muito distantes ficam de fora. Por isso a região de Santa Cruz não tem paradas no projeto e Guaratiba tem só 41 (arquivo 15).
2. **Calendário de dia útil** (serviço identificado como `U_REG` no feed).
3. **Uma viagem representativa por linha.** Cada linha entra uma vez, com uma sequência de paradas, e não com todas as viagens do dia.

Consequências: o grafo mostra a estrutura da rede, não a frequência dos ônibus; linhas com trajetos diferentes de ida e volta ou variações podem aparecer com uma só sequência; e não há horários nem lotação no projeto.

## Identificadores e bairros

Cada parada tem um identificador do feed (por exemplo `5141O00287C0`) e um nome. O **bairro oficial** da parada não vem do GTFS: é calculado cruzando a coordenada da parada com os polígonos do arquivo Limite de Bairros da Prefeitura do Rio (164 polígonos), pelo script 09. Veja o arquivo 08.

Duas paradas ficam ligadas no grafo quando uma viagem passa por elas em sequência (relação `CONNECTS_TO`, com 6.974 pares dirigidos distintos). A leitura do grafo está no arquivo 07.
