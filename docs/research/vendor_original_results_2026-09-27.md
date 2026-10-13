# Indicadores originais MT5 — resultados efetivamente executados

Data: 27/09/2026. Classificação geral: experimental / precisa de mais dados.
Nenhum candidato aprovado para paper trading por esta auditoria. Não houve ordens.

**Atualização posterior à matriz:** a divergência Gold descrita abaixo foi
reproduzida com ticks reais e eliminada ao solicitar CopyBuffer a cada tick.
15.574 linhas de objetos coincidem exatamente entre oculto corrigido e visual,
incluindo entrada/SL/TP. O default do registrador passou a CalculateEveryTick=true.
Os lotes anteriores permanecem diagnósticos de amostragem esparsa, não captura
certificada do comportamento intrabar. Gap Drive com defaults, ticks reais e
cálculo por tick ainda não gerou objetos na semana 21–26/09. Ver o relatório de
aquisição `broker_data_followup_2026-09-27.md` para dados e bloqueios restantes.

## Escopo e evidência

Foram carregados os EX5 originais no Strategy Tester local por iCustom, com seus
defaults, por meio de VendorSignalAudit. Não são reproduções Python. O registrador
amostra buffers de barras concluídas no primeiro tick da barra seguinte e captura
objetos com o horário em que foram observados. Foram concluídos dois lotes de
sete pilotos, uma matriz de 18 casos e uma comparação Gold visual/oculto de um dia.
Também foi executado um piloto 13X com apenas um buffer para diagnosticar a captura.
O controle nativo EMA integra os pilotos; não fornece comparação econômica.

Os pilotos de ouro usam 20–25/04/2026; a matriz usa 04–09/05/2026. Gap Drive usa
US100.s em setembro (14–19 e 21–26). Os intervalos são curtos e não são períodos
fora da amostra suficientes para uma conclusão financeira. Não houve otimização.
XAUUSD.s é spot/CFD e US100.s é CFD: não equivalem a contratos NQ ou GC.
Horários são brutos do servidor. Ticks são GERADOS, não uma certificação bid/ask
histórica de execução. Comissões, slippage, latência e swaps não foram simulados.

## Resultados por família

| Original | Timeframes na matriz | Resultado técnico | Classificação / impedimento |
|---|---|---|---|
| 13X | M5, M15, H1 | 6 buffers disponíveis; nenhuma revisão nas rechecagens | Experimental; mapear buffers de entrada/saída |
| 100 Pips | M5, M15, H1 | 4 buffers disponíveis; nenhuma revisão; objetos de níveis | Experimental; H1 recomendado, demais TF são sensibilidade |
| Duck V4 | M5, M15, H1 | 104, 58 e 27 revisões de buffers, respectivamente | Experimental; separar cor/linha auxiliar de gatilho |
| Gold Fakeout | M5, M10, M15, H1 | 76, 47, 35 e 3 candidatos novos; buffers sem revisões | Precisa resolver diferença visual/oculto; M10 recomendado |
| London Box | M5, H1 | M5 recusado pelo original; H1 captura 70 objetos únicos | Experimental em H1; M5 rejeitado por incompatibilidade |
| Nasdaq Gap Drive | M1, M5, M15 | Um buffer auxiliar; nenhum objeto de sinal | Precisa de configuração/sessão verificadas e mais dados |
| Caixa Americana | Nenhum | Não executado: falta histórico WIN/B3 adequado | Precisa de dados; não substituir WIN por ouro |

London M15 não foi executado após a mensagem explícita exigindo H1 em M5.
Ausência de sinal do Gap Drive não demonstra ausência de vantagem. Seu default de
abertura 01:00 não foi certificado como abertura correta do Nasdaq: a série
US100 observada começa às 01:05. É necessário verificar fuso, horário de verão,
sessão e identificação do símbolo antes de comparar configurações. Não escolher
um horário por maximizar lucro no mesmo período.

No primeiro piloto Gold M10 houve 39 candidatos novos; no segundo, 47. Nos quatro
TF da matriz, o primeiro aparecimento foi uma barra depois do horário desenhado
(300, 600, 900 e 3.600 segundos). Isso não é por si só repaint: é disponibilidade
no fechamento. Executar retroativamente no início da barra desenhada criaria
look-ahead. Objetos já presentes na primeira fotografia foram excluídos como
entradas novas. Candidatos a entrada não são trades executados ou independentes.

### Divergência visual/oculto no Gold

Comparação M10, 04–05/05/2026, mesmas configurações salvo Visual:

- CSV de buffers idêntico por SHA256.
- 15.574 linhas lógicas de objetos em cada modo, sem objetos exclusivos de um modo.
- 4.948 linhas com preços diferentes; 2.474 também diferem em price1.
- Horários, nomes, tipos e textos iguais; diferença máxima de preço 0,136039604.
- Inclui coordenadas de entrada, SL e TP, não apenas decoração.
- Em cada modo: 138 fotografias, 120 objetos únicos, 11 candidatos novos.

A causa NÃO foi determinada. Concordância de contagens e textos não certifica
preços de execução. Não utilizar rótulos GAIN/LOSS como lucro realizável. Antes de
validar o Gold, repetir em ticks reais e confrontar primeiros sinais/níveis com
quotes gravadas, idealmente em coleta prospectiva demo, sem ordens automáticas.

No Duck, revisão de buffers auxiliares não prova repaint de entradas. No London,
alterações da caixa enquanto ela se forma também não provam isso. Inversamente,
zero revisões em 12 barras seguintes não certifica ausência de repaint posterior,
intrabar ou em objetos não mapeados. Falhas/crashes de 26/09 foram superados nesta
captura após reinicialização/recompilação; sua causa permanece não demonstrada.

## Ranking e combinações

Não há ranking econômico defensável para ouro ou Nasdaq. Retorno, Sharpe,
Sortino, drawdown, PF, expectancy e métricas classificatórias permanecem NÃO
ESTIMADOS para os originais. Não há evidência de ganho incremental entre eles.
Prioridade de investigação técnica, não recomendação de compra/venda:

1. Mapear 13X e 100 Pips H1 contra as instruções do fornecedor e timestamps causais.
2. Mapear London H1 e estados H4/H1/M5 do Duck sem usar vela superior ainda aberta.
3. Resolver divergência Gold M10 antes de otimizar EMA/Bollinger/SL/TP.
4. Corrigir contrato de sessão do Gap Drive antes de avaliar Nasdaq.
5. Obter WIN para Caixa Americana, mantendo escopo B3 separado.

Testar combinações somente após certificação de cada gatilho. Features candidatas
intermercado (dólar, yields, prata, petróleo, VIX, semicondutores) exigem timestamps
de disponibilidade e fontes históricas sincronizadas; preços de screenshots não
são dados suficientes. Não afirmar que essas combinações melhoram os originais.

## Reprodução

Fonte: mql5/Experts/VendorSignalAudit.mq5. Última compilação: zero erros/avisos,
registrada em output/vendor_signal_audit_compile_20260927_v2.log. Family 7 é
controle EMA nativo; 0–6 são os originais. Nenhum OrderSend/CTrade é usado.
Configs e inputs: configs/mt5/pilot27*.ini e .set. .set deve estar no
MQL5/Profiles/Tester da instalação usada; EX5 originais em Indicators/Purchased,
registrador em Experts/Research. Os caminhos locais do runner precisam ser
adaptados para outro computador. Fechar MT5 normalmente antes de rodar o lote.
O script nunca força encerramento; timeout exige inspeção humana.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_mt5_vendor_pilots.ps1 -Batch pilot27v2
# Matriz: escolher cada caso, excluindo london_M15, por exemplo:
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_mt5_vendor_pilots.ps1 -Batch pilot27matrix -Cases gold_M10
python scripts/summarize_mt5_vendor_audits.py output/vendor_indicator_research/pilot27matrix
python -m pytest tests/test_vendor_signal_audit.py tests/test_vendor_objects.py tests/test_vendor_capture_modes.py -q
```

Resultados brutos, análises JSON e journals estão em
output/vendor_indicator_research/{pilot27,pilot27v2,pilot27matrix,pilot27hidden,pilot27visual}.
Matriz consolidada: pilot27matrix/summary.md e summary.json. Comparação:
gold_visual_vs_hidden_20260927.json. Revisões do parser de journal isolam o início
do caso atual: warnings cumulativos de London M5 não devem contaminar H1/Gap.

## Experimento econômico ainda necessário

Exigir ao menos 250 sessões por instrumento e preferir 3–5 anos; usar ticks reais
bid/ask, especificações do contrato e custos da conta. Reservar holdout final
intocado. Walk-forward proposto: treino 12 meses, validação 3, teste 3, passos de
3 meses; embargo/purga no mínimo pelo maior horizonte do label/posição. Ajustar
scalers, seleção de features, modelos e limiares apenas no treino/validação.
Não reabrir o holdout para corrigir um resultado ruim.

Registrar todas as variantes, inclusive negativas. Comparar baseline sem filtro,
regra simples e modelos regularizados antes de boosting. Executar ablação por
família, testes com parâmetros vizinhos, anos/regimes, custos aumentados e atraso.
Bootstrap em blocos por sessão e correção de múltiplos testes; amostra pequena,
dependência de um período ou lucro concentrado em poucos trades impedem aprovação.
Buy-and-hold deve usar contrato/rolagem comparáveis; não comparar CFD intraday
alavancado com um índice sem custos. Saídas ambíguas na mesma vela exigem ticks
ou tratamento conservador explicitamente separado.

Conclusão: auditoria técnica executada; validação econômica dos originais NÃO
concluída. Não existe nesta evidência base para prometer rentabilidade ou emitir
recomendações operacionais confiáveis.
