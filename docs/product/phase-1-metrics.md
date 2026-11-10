# Metricas de acompanhamento - Fase 1

Atualizado em: 13/08/2026

## Metricas semanais

| Metrica | Fonte no sistema | Por que importa |
| --- | --- | --- |
| Aulas concluidas | `LessonProgress` | Mede ativacao da Escola |
| Cursos iniciados | Cursos com pelo menos uma aula concluida | Mostra se o usuario saiu da vitrine |
| Sinais gerados | Alertas e recomendacoes registradas | Mede uso do terminal |
| Sinais bloqueados por dados | Quality gate / `NO_TRADE` | Mede disciplina e confiabilidade |
| Sinais bloqueados por risco | Risk engine / decision card | Evita automacao perigosa |
| Recomendacoes registradas | Historico da Mesa IA | Alimenta memoria temporal |
| Acerto 5d | Scoreboard da Mesa IA | Mede calibracao real, nao narrativa |
| Drawdown simulado | Paper simulator / validacao | Mede risco operacional |
| Usuarios ativos | Login/uso em rotas principais | Mede piloto real |
| Erros de dados/API | Health check e logs | Mostra gargalos de infra |

## Rotina de revisao

Toda sexta-feira:

1. Exportar ou consultar os numeros da semana.
2. Separar aprendizado, terminal e inteligencia.
3. Ver quais sinais foram bloqueados e se o bloqueio estava correto.
4. Revisar 3 decisoes registradas com maior confianca.
5. Revisar 3 casos em que o sistema retornou `NO_TRADE`.
6. Atualizar backlog da semana seguinte.

## Limites para piloto

| Area | Limite recomendado |
| --- | --- |
| Usuarios | 5 a 10 |
| Watchlist por usuario | 10 a 20 ativos |
| Regras por usuario | 5 a 10 |
| IA | Limite mensal por usuario ou cache obrigatorio |
| Automacao | Apenas monitoramento, alerta e paper trading |
| Broker real | Fora da Fase 1 |

## Sinal verde para ir para Fase 2

- Pelo menos 5 usuarios completaram uma aula ou abriram uma trilha.
- Pelo menos 3 usuarios criaram watchlist ou analisaram ativo.
- Mesa IA registrou leituras suficientes para iniciar revisao.
- Nao houve erro recorrente de dados ou login bloqueando uso.
- Usuarios entenderam que o produto e apoio a decisao, nao promessa de sinal.

