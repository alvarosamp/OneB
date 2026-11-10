# Fase 1 - Organizacao e MVP acompanhado

Atualizado em: 13/08/2026

## Meta

Deixar o OneB Market acompanhavel pelo responsavel do projeto e testavel por 5 a 10 usuarios piloto em 2 a 3 semanas.

## Quadro de acompanhamento

| Epico | Objetivo | Status | Dono sugerido | Evidencia de pronto |
| --- | --- | --- | --- | --- |
| Produto | Organizar fluxo publico, login e experiencia operacional | Em andamento | Produto/engenharia | Usuario entende o que e vitrine e o que e terminal real |
| Escola | Conectar trilhas, aulas e progresso ao LMS | Em andamento | Produto/conteudo/engenharia | `/aprendizado` lista cursos reais e `/aulas/:slug` marca progresso |
| Inteligencia | Acompanhar decisoes, qualidade, memoria e bloqueios | Em andamento | Quant/engenharia | Mesa IA registra leitura e mostra confiabilidade |
| Indicadores | Criar catalogo de setups testaveis | A fazer | Quant/engenharia | Cada setup tem regra, invalidacao, filtro e backtest |
| HFT/automacao | Manter como pesquisa/paper trading, sem execucao real | A fazer | Engenharia/risco | Documento deixa claro o caminho seguro ate broker |
| Infra | Garantir ambiente local/piloto observavel | A fazer | Engenharia | Health check, scheduler, dados e logs acompanhados |

## Semana 1

| Frente | Tarefa | Resultado |
| --- | --- | --- |
| Produto | Separar vitrine publica de area autenticada | `/aulas` como marketing; `/aprendizado` e terminal protegidos |
| Escola | Conectar lista real de cursos ao LMS | Cursos publicados aparecem com progresso por usuario |
| Escola | Revisar slugs e links das trilhas | Links apontam para cursos existentes |
| Produto | Criar backlog de conteudo | Conteudo inicial priorizado |
| Infra | Rodar build/testes relevantes | Risco tecnico conhecido |

## Semana 2

| Frente | Tarefa | Resultado |
| --- | --- | --- |
| Escola | Escrever conteudo minimo das aulas obrigatorias | Usuario piloto consegue estudar uma trilha inteira |
| Inteligencia | Definir metricas de acompanhamento | Painel/rotina semanal sabe o que medir |
| Indicadores | Criar catalogo v1 de setups | Regras prontas para virar backtest |
| Produto | Preparar roteiro de piloto | 5 a 10 usuarios sabem o que testar |

## Semana 3

| Frente | Tarefa | Resultado |
| --- | --- | --- |
| Piloto | Rodar uso guiado com 5 a 10 usuarios | Feedback real por fluxo |
| Escola | Ajustar aulas e progresso com base no uso | Menos friccao no aprendizado |
| Inteligencia | Auditar sinais/recomendacoes geradas | Identificar ruido, bloqueios e falsos positivos |
| Produto | Decidir escopo da Fase 2 | Backlog ordenado por impacto |

## Criterios de pronto da Fase 1

- Usuario novo consegue se cadastrar, entrar e abrir a area operacional.
- Escola autenticada lista cursos reais do LMS.
- Curso detalhe permite assistir/ver conteudo, marcar aula concluida e ver progresso.
- Backlog de conteudo existe e separa obrigatorio, futuro, exercicio e checklist.
- Indicadores e HFT estao documentados como frentes de produto, sem promessa de execucao automatica.
- Rotina semanal de metricas foi definida.
- Pelo menos um build ou teste relevante foi executado antes do piloto.

