# Captura dos indicadores originais

`mql5/Experts/VendorSignalAudit.mq5` é um registrador, não um robô de negociação.
Recusa inicialização fora do Strategy Tester e não contém OrderSend/CTrade.
Foi compilado no MetaEditor com zero erros e zero avisos em 2026-09-26.

## Execução

1. No navegador MT5, atualizar Consultor expert e selecionar
   Research/VendorSignalAudit → Teste.
2. Escolher símbolo da corretora, timeframe e intervalo histórico. Para o teste
   inicial, usar apenas uma semana antes de ampliar a captura.
3. Family: 0 Gold Fakeout, 1 London Box, 2 13X, 3 100 Pips,
   4 DuckV4, 5 Nasdaq Gap Drive, 6 Caixa Americana.
4. Objetos são capturados tanto no modo oculto quanto no visual. Manter
   CalculateEveryTick=true: esta correção eliminou a divergência Gold na amostra
   de 04/05/2026. Comparar ambos antes de confiar em novos sinais/instrumentos.
   Usar ticks reais quando disponíveis; caso contrário declarar ticks gerados.
5. Os indicadores são carregados com seus defaults originais. Alterar Family
   não altera outros parâmetros ocultos. Não misturar esse experimento com
   otimizações dos parâmetros das reproduções Python.
6. Os arquivos ficam no MQL5/Files do agente isolado do testador, com prefixo
   RunLabel + família + símbolo + timeframe. Não habilitar cloud agents.

Os buffers são amostrados no primeiro tick de cada nova barra, apenas para
barras concluídas, e novamente nas 12 barras seguintes por padrão. Os objetos
são fotografados logicamente (nome, texto e coordenadas de preço/tempo) por barra.
Objetos podem descrever a barra em formação ou resultados já conhecidos; **não
usar o timestamp desenhado como se fosse o momento em que o sinal apareceu**.
Usar observed_at para controlar disponibilidade. O fuso é bruto do servidor.

## Análise

```powershell
python scripts/analyze_vendor_signal_audit.py "CAMINHO_DO_AGENT\MQL5\Files\audit_v1_0_XAUUSD.s_PERIOD_M10_buffers.csv" --output output/vendor_indicator_research/original_gold_buffer_audit.json
```

O analisador procura mudanças de valor e aparecimento/desaparecimento de valores
de buffers de barras já fechadas. Buffers indisponíveis são contados à parte.
O mapeamento de cada buffer para compra/venda/saída ainda deve ser verificado
contra os objetos e os vídeos. Revisão de média móvel auxiliar não equivale
automaticamente a repaint do gatilho. Zero revisões não certifica ausência de
repaint: o indicador pode alterar objetos, mudar intrabar ou revisar depois da
janela amostrada. Não calcula PF, lucro ou probabilidade de vitória.

Somente após mapear gatilhos disponíveis em cada observed_at devemos reconstruir
execução a bid/ask, custos, latência e validação fora da amostra.

Referências oficiais:
- https://www.mql5.com/en/docs/indicators/icustom
- https://www.mql5.com/en/docs/chart_operations/chartindicatoradd

Status em 2026-09-27: registrador recompilado e instalado com zero erros/avisos;
pilotos e matriz de 18 casos concluídos. As falhas de 26/09 permanecem documentadas
em `vendor_capture_attempt_2026-09-26.md`, mas não impedem mais esta captura.
A causa dos crashes anteriores não foi demonstrada. Resultados e limitações em
`vendor_original_results_2026-09-27.md`. O teste visual simples, sem o registrador,
não gera esses arquivos automaticamente.
