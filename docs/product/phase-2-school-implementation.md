# Fase 2 - Escola OneB de verdade

Atualizado em: 13/08/2026

## O que foi implementado

A Escola deixou de ser apenas vitrine e ganhou uma primeira versao operacional conectada ao LMS.

## Curriculo v1

Quatro trilhas publicadas pelo seed do LMS:

| Trilha | Slug | Foco |
| --- | --- | --- |
| Fundamentos do mercado americano | `fundamentos` | Mercado, dados, custos, watchlist e rotina inicial |
| Analise tecnica e price action | `analise-tecnica-avancada` | Candles, regime, niveis, indicadores e setup tecnico |
| Gestao de risco e psicologia | `gestao-de-risco-e-psicologia` | Risco, stop, tamanho, circuit breaker, FOMO e NO_TRADE |
| Processo, diario e revisao | `processo-diario-e-revisao` | Diario, invalidacao, falso positivo, revisao semanal e plano individual |

## Estrutura de cada aula

Cada aula agora retorna pela API:

- video/link
- resumo
- checklist
- exercicio pratico
- duracao
- flag de aula obrigatoria
- status de conclusao por usuario

Esses campos sao calculados pelo catalogo pedagogico do backend, sem exigir migracao de banco nesta fase.

## Recomendacao de proxima aula

Endpoint: `GET /api/lms/learning-state`

A recomendacao usa lacunas simples do diario de decisao:

| Lacuna detectada | Aula recomendada |
| --- | --- |
| Decisao sem invalidacao | Tese, gatilho e invalidacao |
| Decisao sem risco | Definindo seu risco maximo |
| Decisao sem gatilho | Tese, gatilho e invalidacao |
| Sem lacuna recente | Primeira aula obrigatoria incompleta |

## Certificado simples

O certificado fica liberado quando:

- todas as aulas obrigatorias publicadas forem concluidas;
- o usuario tiver pelo menos 3 setups praticos registrados na Mesa Tecnica.

Enquanto nao libera, a API retorna o proximo requisito pendente.

## UI atualizada

- `/aprendizado` agora carrega `learning-state`, mostra progresso real, recomendacao e status de certificado.
- `/aulas/:slug` mostra resumo, checklist e exercicio especificos da aula.
- O usuario pode marcar/desmarcar aula concluida.
- A tela de curso manteve simulador simples para pratica de entrada, stop, alvo, risco e R/R.

## Proximos refinamentos

- Persistir anotacoes e respostas dos exercicios por usuario.
- Criar videos/links finais para cada aula.
- Registrar simulacoes feitas dentro do simulador da aula, nao apenas setups da Mesa Tecnica.
- Criar tela visual de certificado com emissao/exportacao.
- Melhorar recomendacao com mais eventos: overtrading, setup sem stop, excesso de indicadores, dados ruins e sinais ignorados.

