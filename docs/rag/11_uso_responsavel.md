---
id: 11_uso_responsavel
titulo: Uso responsável do índice e limites de interpretação
tipo: interno
origem: webapp/views/metodologia.py, webapp/rag/prompts.py, análise dos dados do projeto
url: https://github.com/viniciusemaciel/riomobianalytics
periodo_coberto: 2020–2025
atualizado_em: 2026-11-14
tags: [uso responsável, estigma, viés, probabilidade, limites, decisão, segurança pessoal]
---

## O índice é relativo e não é probabilidade

O índice vai de 0 a 100 e resulta de uma normalização entre as paradas atuais: a parada de maior valor sempre recebe 100. Ele serve para **comparar paradas**. "Índice 80" não significa 80% de chance de nada, e o assistente nunca deve escrever "%" depois dele. O componente do modelo também não é uma probabilidade calibrada, e por isso o índice não indica quando ou onde um tiroteio específico vai ocorrer.

## Tiroteio no entorno não é tiroteio na parada

O alvo do modelo é "houve pelo menos um tiroteio registrado a até 500 m da parada naquele mês". Isso é uma área de cerca de 0,8 km² em torno da parada, e a ocorrência pode ter sido numa rua paralela, numa comunidade vizinha ou numa operação a algumas quadras. O índice descreve o **entorno**, não o ponto de ônibus nem as pessoas que o usam.

## Viés de registro: o que não aparece nos dados

Cada fonte vê uma parte da realidade. O Fogo Cruzado registra tiroteios que consegue captar e verificar, e a cobertura depende dessa capacidade. O 1746 registra quem acessa o canal: áreas com menos acesso ou menos hábito de reclamar podem parecer mais tranquilas do que são. O GTFS descreve o que está no feed, não a rede inteira. Por isso, índice baixo não é "seguro" e ausência de reclamação não é ausência de problema.

## Risco de estigma

Rankings de bairros por tiroteios ou por níveis de risco podem ser lidos como julgamento sobre quem mora ali. O projeto evita isso por regra: descreve **ocorrências registradas**, não comportamento, população ou grupos; cita sempre o período; não atribui violência a comunidades; e o assistente é instruído a não usar rótulos como "perigoso" ou "violento" para bairros. Bairros maiores têm mais ocorrências em números absolutos, e o projeto não calcula taxa por habitante.

## Decisões pessoais e de política pública

O índice **não deve ser usado** para decidir sozinho se uma pessoa pode ou não usar uma parada, escolher uma rota individual ou orientar abordagem policial. O assistente recusa pedidos de conselho pessoal de segurança e remete a fontes oficiais. Para planejamento, o índice é um ponto de partida para investigar: qualquer decisão pública exigiria dados oficiais (como os do ISP-RJ), contexto local e participação de quem vive na região.

## Como o assistente deve apresentar limites

Ao responder sobre risco, o assistente deve: dar o número da ferramenta com o período; dizer em uma frase que é um índice de comparação; e, se perguntarem o porquê de um valor alto, explicar que localização e histórico pesam muito no modelo, sem inventar causas locais. Ao tratar de contexto externo (arquivos 20 a 22), deve dizer de quem é a informação.
