# Tentativa de captura dos originais — 2026-09-26

## Evidência de execução

- London Box: execução exploratória interrompida às 09:57:09 locais. Últimos
  alertas preservados abrangem até 2026-05-29. Não é um teste completo ou econômico.
- Log anterior preservado em
  `output/vendor_indicator_research/mt5_gold_completed_london_partial_20260926.log`.
- VendorSignalAudit, Family=2 (13X), XAUUSD.s H1, intervalo solicitado
  2026-04-20 a 2026-04-25, defaults originais, 12 buffers e 12 barras fechadas.
- Primeira execução: visual, Cada tick (ticks gerados), iniciou 10:02:40.
  Agente desconectou 10:02:47; sem captura utilizável.
- Segunda execução: mesmo intervalo e indicador, sem visualização, aproximadamente
  10:03:55; também sem captura utilizável.
- Arquivos observados: buffers=0 bytes; objetos=54 bytes. Não foram analisados
  como amostra válida, nem usados para afirmar ausência de repaint.

## Diagnóstico observado

Eventos Application do Windows confirmam falhas de `metatester64.exe`
versão 5.0.0.6193 no módulo `ntdll.dll`:

- evento 1000 às 10:02:41: exceção 0xc000041d;
- evento 1000 às 10:03:56: exceção 0xc0000005.

O próprio terminal passou a exibir "Não está respondendo" durante tentativa
posterior de abrir Parâmetros de entrada. Não foi encerrado à força, não foram
enviadas ordens e Algotrading não foi habilitado.

Não há evidência suficiente para atribuir a causa ao EX5, ao registrador,
à compatibilidade da versão do terminal ou a outro componente.

## Código e verificação

O analisador Python passou nos dois testes locais. Foi necessário executar com
permissão de criação de temporários; erros anteriores eram de permissões.
Adicionados marcadores INIT/LOAD/FIRST TICK e flush dos cabeçalhos ao fonte do
registrador para diagnóstico. Essa revisão ainda precisa ser compilada e
instalada antes de repetir; o EX5 existente não contém esses marcadores.

## Próxima sequência após recuperar o terminal

1. Reabrir MT5 sem habilitar execução automática; conferir conexão.
2. Compilar/instalar revisão instrumentada e executar 13X H1 por um dia,
   BufferCount=1, sem visualização; preservar log imediatamente.
3. Comparar com um indicador nativo e depois com original testado diretamente,
   para separar falha do agente de falha da integração iCustom.
4. Apenas após captura não vazia, expandir buffers e janela. Em seguida,
   repetir com 100 Pips H1 e Duck M5, e outros timeframes como experimentos
   separados. Captura sem visual não verifica sinais baseados em objetos.
5. Mapear gatilhos e saídas antes de qualquer simulação de lucro líquido.

Classificação atual: **experimental, bloqueado tecnicamente na captura**.
Nenhum indicador original está aprovado para paper trading por estas tentativas.
