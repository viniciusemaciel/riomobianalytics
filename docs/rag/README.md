# Base de conhecimento do assistente (RAG) — convenções

Esta pasta guarda os textos que o assistente "Pergunte ao RioMobi" consulta para explicar o projeto e dar contexto. **Este README não é indexado.** Os demais arquivos são.

## Princípio

- **Números vivos vêm das ferramentas** (Neo4j/MongoDB): índice, níveis, contagens, rankings. Os textos daqui explicam o porquê, o como e o contexto.
- Quando um arquivo traz um número (ex.: 6.426 paradas, AUC 0,71), é o valor do período da base (2020–2025) e serve para explicar. Se a pergunta pede o valor atual de uma parada, bairro ou linha, usar a ferramenta.
- **Conteúdo externo nunca é dado do projeto.** Os arquivos `2x_contexto_*` resumem fontes públicas com paráfrase, link e data de acesso. O assistente deve apresentá-los como "segundo [fonte]".

## Tipos de arquivo

| Prefixo | Tipo | Conteúdo |
|---|---|---|
| 01 a 16 | interno | documentação do projeto escrita a partir do repositório (scripts, notebooks, artifacts, app) |
| 20 a 22 | externo | contexto de segurança pública no período da base, paráfrase de fontes citadas |
| `_` no início do nome | não indexado | material de apoio para humanos (ex.: `_referencias.md`) |

## Cabeçalho (front matter) de cada arquivo

```
---
id: identificador estável (igual ao nome do arquivo, sem .md)
titulo: título legível
tipo: interno | externo
origem: de onde vem o conteúdo
url: link da fonte (externos)
periodo_coberto: período dos dados ou do assunto
atualizado_em: AAAA-MM-DD
acessado_em: AAAA-MM-DD (externos)
tags: [palavras, de, busca]
---
```

## Regras de escrita

1. Cada seção `##` é um chunk: de **40 a 400 palavras** (o ideal é 100 a 300), autossuficiente (repete o termo principal em vez de dizer "como acima"). Seções curtas só quando o assunto é pontual.
2. Títulos de seção dizem o assunto ("Por que o índice não é uma probabilidade"), não só "Observações".
3. Externos: paráfrase, no máximo uma citação curta (menos de 15 palavras) por fonte, sempre com link. Sem linguagem que estigmatize bairros, comunidades ou pessoas.
4. O conteúdo é informação útil para responder perguntas sobre o projeto e a região. Não entram auditoria do próprio projeto, lista de erros nem assuntos que o projeto não usa (por exemplo, grupos armados).

## Quando atualizar cada arquivo

| Se mudar... | Atualizar |
|---|---|
| período ou arquivo do Fogo Cruzado | 01, 04, 05, 06, 08, 13, 22, 15, 16 |
| arquivo do 1746 | 01, 03, 05, 13, 15 |
| GTFS (nova versão da rede) | 02, 07, 09 |
| pesos, fórmula ou níveis do índice | 05, 12, 13 |
| modelo (retreino, métricas, features) | 06, 05, 13 |
| ferramentas ou prompt do assistente | 10, 11, 13 |
| telas ou controles do aplicativo | 01, 14 |
| rodar o script 07 em nova data | 05 (seção da data de referência), 06 |
| novo relatório do Fogo Cruzado | 21, `_referencias.md` |
| novos eventos no período ou revisão de balanços | 22, `_referencias.md` |
