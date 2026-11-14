---
id: 15_regioes_da_cidade
titulo: Regiões da cidade — perfil das áreas de planejamento e regiões de planejamento
tipo: interno
origem: Limite de Bairros da Prefeitura do Rio (campos área de planejamento e região de planejamento), paradas do GTFS, base do Fogo Cruzado e chamados do 1746 do projeto
url: https://github.com/viniciusemaciel/riomobianalytics
periodo_coberto: 2020–2025
atualizado_em: 2026-11-14
tags: [região, zona, área de planejamento, AP, região de planejamento, RP, Zona Norte, Zona Oeste, Zona Sul, Centro, Barra, Jacarepaguá, bairros, contexto regional]
---

## Como a cidade é dividida

A Prefeitura do Rio organiza os 164 bairros do arquivo Limite de Bairros em **5 áreas de planejamento (AP)** e, dentro delas, em **regiões de planejamento (RP)**. O projeto usa essa divisão para dar contexto regional a uma parada ou a um bairro.

| AP | Nome usual | Regiões de planejamento |
|---|---|---|
| AP 1 | Centro | Centro |
| AP 2 | Zona Sul e Grande Tijuca | Zona Sul, Tijuca |
| AP 3 | Zona Norte | Ramos, Penha, Inhaúma, Méier, Madureira, Ilha do Governador, Pavuna |
| AP 4 | Barra e Jacarepaguá | Barra da Tijuca, Jacarepaguá |
| AP 5 | Zona Oeste | Bangu, Campo Grande, Santa Cruz, Guaratiba |

Os números deste arquivo descrevem 2020 a 2025 e servem para situar uma pergunta. Para o valor de uma parada, de um bairro ou de um ano específico, as ferramentas do assistente são a fonte.

## Perfil das cinco áreas de planejamento (2020 a 2025)

Tiroteios contados uma vez, no bairro oficial onde ocorreram (cidade do Rio).

| AP | Bairros | Área (km²) | Paradas | Tiroteios | Tiroteios por km² | Com ação policial | 2020 → 2025 |
|---|---|---|---|---|---|---|---|
| AP 1 Centro | 16 | 34 | 511 (8%) | 809 (6%) | 23,5 | 31% | 227 → 54 |
| AP 2 Zona Sul e Tijuca | 25 | 100 | 847 (13%) | 1.389 (11%) | 13,8 | 25% | 349 → 207 |
| AP 3 Zona Norte | 80 | 203 | 2.516 (39%) | 6.327 (50%) | 31,1 | 33% | 1.295 → 865 |
| AP 4 Barra e Jacarepaguá | 19 | 294 | 1.346 (21%) | 1.962 (16%) | 6,7 | 26% | 258 → 228 |
| AP 5 Zona Oeste | 24 | 572 | 1.206 (19%) | 2.146 (17%) | 3,8 | 23% | 595 → 212 |

Leitura: a Zona Norte (AP 3) concentra metade dos tiroteios registrados na cidade e a maior densidade por área, e é também onde está a maior parte das paradas. Todas as áreas tiveram menos tiroteios em 2025 do que em 2020; a queda foi maior no Centro (cerca de 76%) e na Zona Oeste (64%) e menor em Barra e Jacarepaguá (12%). A parcela com ação policial varia de 23% (Zona Oeste) a 33% (Zona Norte).

## Regiões de planejamento: tiroteios e paradas

| RP (AP) | Paradas | Tiroteios 2020–2025 | % da cidade | 2020 → 2025 | Com ação policial |
|---|---|---|---|---|---|
| Madureira (3) | 710 | 1.844 | 14,6% | 286 → 365 | 24% |
| Bangu (5) | 791 | 1.642 | 13,0% | 528 → 125 | 26% |
| Jacarepaguá (4) | 712 | 1.587 | 12,6% | 241 → 160 | 26% |
| Pavuna (3) | 339 | 1.115 | 8,8% | 260 → 147 | 38% |
| Penha (3) | 324 | 1.024 | 8,1% | 208 → 89 | 35% |
| Tijuca (2) | 347 | 1.001 | 7,9% | 236 → 163 | 24% |
| Méier (3) | 470 | 894 | 7,1% | 186 → 86 | 34% |
| Centro (1) | 511 | 809 | 6,4% | 227 → 54 | 31% |
| Ramos (3) | 228 | 697 | 5,5% | 149 → 98 | 46% |
| Inhaúma (3) | 176 | 546 | 4,3% | 166 → 49 | 29% |
| Zona Sul (2) | 500 | 388 | 3,1% | 113 → 44 | 29% |
| Barra da Tijuca (4) | 634 | 375 | 3,0% | 17 → 68 | 25% |
| Campo Grande (5) | 374 | 236 | 1,9% | 50 → 33 | 12% |
| Ilha do Governador (3) | 269 | 207 | 1,6% | 40 → 31 | 35% |
| Santa Cruz (5) | 0 | 204 | 1,6% | 16 → 37 | 14% |
| Guaratiba (5) | 41 | 64 | 0,5% | 1 → 17 | 14% |

Madureira e Barra da Tijuca são as únicas regiões com mais tiroteios em 2025 do que em 2020. Ramos tem a maior parcela de tiroteios com ação policial (46%).

## Exposição das paradas por região

A exposição de uma parada é o número de tiroteios a até 500 m dela de 2020 a 2025 (arquivo 08). A mediana por parada muda muito entre regiões: cerca de 20 em Penha, Ramos, Inhaúma e Tijuca; 11 no Centro; 5 na Zona Sul; 2 na Barra da Tijuca e na Ilha do Governador; e 1 em Campo Grande e Guaratiba. Em Centro, Méier, Penha, Ramos e Inhaúma praticamente todas as paradas tiveram ao menos um tiroteio no raio; na Barra da Tijuca e em Campo Grande, de 25% a 29% das paradas não tiveram nenhum.

**Santa Cruz não tem paradas no projeto** e Guaratiba tem só 41: o feed de ônibus foi recortado num raio de 40 km do Centro (arquivo 02), o que deixa de fora boa parte do extremo oeste. Os tiroteios dessas regiões existem na base, mas não há paradas para associá-los.

## Perfil das reclamações do 1746 por área

Parcela de cada serviço nas reclamações ligadas às paradas de cada área (2020 a 2025):

| AP | Limpeza | Iluminação | Conservação de vias | Segurança Pública | Trânsito |
|---|---|---|---|---|---|
| AP 1 Centro | 29% | 19% | 12% | 32% | 8% |
| AP 2 Zona Sul e Tijuca | 40% | 22% | 13% | 19% | 7% |
| AP 3 Zona Norte | 45% | 28% | 14% | 9% | 4% |
| AP 4 Barra e Jacarepaguá | 35% | 31% | 18% | 13% | 3% |
| AP 5 Zona Oeste | 36% | 29% | 21% | 10% | 4% |

No Centro, quase um terço das reclamações é de Segurança Pública, que no 1746 é sobretudo fiscalização da Guarda Municipal e ordem urbana, não crime (arquivo 03). Na Zona Oeste pesam mais conservação de vias e iluminação. A AP 2 tem o maior número de reclamações por parada (cerca de 6), e as AP 4 e 5 o menor (cerca de 2,5). Mais reclamações indicam mais uso do canal, não necessariamente mais problemas.

## Bairros de cada região de planejamento

- **Centro (AP 1):** Benfica, Caju, Catumbi, Centro, Cidade Nova, Estácio, Gamboa, Lapa, Mangueira, Paquetá, Rio Comprido, Santa Teresa, Santo Cristo, Saúde, São Cristóvão, Vasco da Gama.
- **Zona Sul (AP 2):** Botafogo, Catete, Copacabana, Cosme Velho, Flamengo, Glória, Gávea, Humaitá, Ipanema, Jardim Botânico, Lagoa, Laranjeiras, Leblon, Leme, Rocinha, São Conrado, Urca, Vidigal.
- **Tijuca (AP 2):** Alto da Boa Vista, Andaraí, Grajaú, Maracanã, Praça da Bandeira, Tijuca, Vila Isabel.
- **Ramos (AP 3):** Bonsucesso, Manguinhos, Maré, Olaria, Ramos.
- **Penha (AP 3):** Brás de Pina, Cordovil, Jardim América, Parada de Lucas, Penha, Penha Circular, Vigário Geral.
- **Inhaúma (AP 3):** Complexo do Alemão, Del Castilho, Engenho da Rainha, Higienópolis, Inhaúma, Maria da Graça, Tomás Coelho.
- **Ilha do Governador (AP 3):** Bancários, Cacuia, Cidade Universitária, Cocotá, Freguesia (Ilha), Galeão, Jardim Carioca, Jardim Guanabara, Moneró, Pitangueiras, Portuguesa, Praia da Bandeira, Ribeira, Tauá, Zumbi.

## Bairros de cada região de planejamento (continuação)

- **Méier (AP 3):** Abolição, Cachambi, Encantado, Engenho Novo, Engenho de Dentro, Jacarezinho, Jacaré, Lins de Vasconcelos, Méier, Piedade, Pilares, Riachuelo, Rocha, Sampaio, São Francisco Xavier, Todos os Santos, Água Santa.
- **Madureira (AP 3):** Bento Ribeiro, Campinho, Cascadura, Cavalcanti, Colégio, Engenheiro Leal, Honório Gurgel, Irajá, Madureira, Marechal Hermes, Osvaldo Cruz, Quintino Bocaiúva, Rocha Miranda, Turiaçú, Vaz Lobo, Vicente de Carvalho, Vila Kosmos, Vila da Penha, Vista Alegre.
- **Pavuna (AP 3):** Acari, Anchieta, Barros Filho, Coelho Neto, Costa Barros, Guadalupe, Parque Anchieta, Parque Colúmbia, Pavuna, Ricardo de Albuquerque.
- **Jacarepaguá (AP 4):** Anil, Cidade de Deus, Curicica, Freguesia (Jacarepaguá), Gardênia Azul, Jacarepaguá, Pechincha, Praça Seca, Tanque, Taquara, Vila Valqueire.
- **Barra da Tijuca (AP 4):** Barra da Tijuca, Camorim, Grumari, Itanhangá, Joá, Recreio dos Bandeirantes, Vargem Grande, Vargem Pequena.
- **Bangu (AP 5):** Bangu, Campo dos Afonsos, Deodoro, Gericinó, Jabour, Jardim Sulacap, Magalhães Bastos, Padre Miguel, Realengo, Senador Camará, Vila Kennedy, Vila Militar.
- **Campo Grande (AP 5):** Campo Grande, Cosmos, Inhoaíba, Santíssimo, Senador Vasconcelos.
- **Santa Cruz (AP 5):** Paciência, Santa Cruz, Sepetiba.
- **Guaratiba (AP 5):** Barra de Guaratiba, Guaratiba, Ilha de Guaratiba, Pedra de Guaratiba.

## Como usar o contexto regional numa resposta

Quando a pergunta é sobre uma parada ou um bairro, o assistente pode situá-lo na sua região em uma ou duas frases, depois de responder com os dados das ferramentas: por exemplo, "Bangu fica na RP Bangu, na Zona Oeste (AP 5), região que teve uma das maiores quedas de tiroteios entre 2020 e 2025". O contexto regional complementa, não substitui, o número da parada ou do bairro.

As diferenças entre regiões descrevem **ocorrências registradas** e uso do 1746, não as pessoas que vivem nelas. Regiões maiores e com mais paradas tendem a somar mais ocorrências, e o projeto não calcula taxas por habitante. O assistente não usa rótulos como "região perigosa".
