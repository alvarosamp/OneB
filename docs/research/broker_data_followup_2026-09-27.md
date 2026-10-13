# Dados e correção da captura — 27/09/2026

## Avanço verificado

Conexão HonorPro-Server já autenticada consultada sem credenciais e sem ordens.
Coletor: scripts/probe_mt5_history.py. Solicitação de barras desde 2021; o servidor
retornou apenas os intervalos abaixo. Não interpretar retorno limitado como prova
de que nenhum histórico adicional existe na corretora; pode haver limite/cache.

| Símbolo | Barras M1 | Datas retornadas | Dias distintos com barras |
|---|---:|---|---:|
| XAUUSD.s | 24.659 | 02–25/09/2026 | 18 |
| XAUUSD24_7.s | 34.661 | 02–27/09/2026 | 26 |
| US100.s | 12.885 | 14–25/09/2026 | 10 |
| GC.Z26 | 10.849 | 02–11/09/2026 | 8 |

Dias distintos não são calendário oficial de sessões; incluem dias parciais e,
no produto 24/7, finais de semana. Não fundir esse produto com XAUUSD.s.
Arquivos e especificações com SHA256:
D:/OneB/market-data/mt5/coverage-20260927/rates/coverage.json.
Preservados os exports M5 anteriores mais extensos; M1 não os substitui.

### Ticks bid/ask realmente obtidos

Uma hora por sonda, 16:00–17:00 no domínio bruto dos timestamps do servidor:

| Símbolo / data | Ticks | Quotes válidas | Spread mediano em preço |
|---|---:|---:|---:|
| XAUUSD.s 25/09/2026 | 19.875 | 19.875 | 0,26 |
| XAUUSD.s 04/05/2026 | 20.484 | 20.484 | 0,31 |
| US100.s 25/09/2026 | 19.736 | 19.736 | 0,70 |

Arquivos CSV.gz brutos, incluindo time_msc e flags, e manifests em subpastas
ticks-recent, ticks-gold-may e ticks-us100 do diretório de cobertura.
Spreads não são custo total: comissão, slippage e latência continuam desconhecidos.
A primeira consulta a ticks muito antigos não terminou em tempo razoável e o
coletor foi interrompido; nenhuma ausência de dados é inferida desse timeout.
Consultas posteriores foram isoladas, limitadas a 45 segundos por processo e
persistidas incrementalmente. Estes trechos não certificam cobertura integral.

### GC.Z26 não certificado como GC de bolsa

O nome e descrição referem dezembro de 2026, mas symbol_info retorna tick_size
0,01, tick_value 1 USD e volume_min 0,01. O GC COMEX padrão tem variação mínima
0,10 USD/onça e contrato 100 onças, equivalente a 10 USD por tick. A discrepância
impede relabelar este instrumento da corretora como feed nativo CME. Não foi
afirmado que a corretora fornece acesso direto à bolsa.
[Especificação CME](https://www.cmegroup.com/trading/metals/files/fact-card-gold-futures-options.pdf).
Nenhum NQ/MNQ ou WIN apareceu nos símbolos disponíveis nesta conexão.

## Gold: causa da divergência de captura identificada

Teste original Gold M10 em 04–05/05/2026 com Model=4: 326.727 ticks e 138 barras.
Hidden sem recálculo a cada tick versus visual: 4.948 linhas diferentes, máximo
0,138217822 em preço. Hidden com CalculateEveryTick=true versus visual:
15.574 linhas lógicas idênticas, zero diferenças, inclusive preço/tempo/texto.

Isso demonstra a causa da discrepância nesta amostra: frequência de cálculo do
registrador. No testador oculto, indicadores normalmente calculam sob demanda;
no visual, recalculam em cada tick. A correção solicita CopyBuffer em todo OnTick,
mantendo a fotografia de barras fechadas somente no início da barra seguinte.
[Documentação oficial MQL5](https://www.mql5.com/en/docs/runtime/testing).

Evidência: output/vendor_indicator_research/gold_real_forced_vs_visual_20260927.json.
Capturas: pilot27real, pilot27realvisual e pilot27realforced. Compilações v3–v7
sem erros/avisos. Os EX5 comprados não foram alterados; apenas o registrador.
Esta concordância não demonstra rentabilidade, ausência universal de repaint ou
captura exata de todos os sinais intrabar.

### Recaptura concluída

17 combinações executadas com Model=4 e CalculateEveryTick=true, no lote
pilot27cert. O nome do lote não é certificação econômica. Relatório completo:
output/vendor_indicator_research/pilot27cert/summary.md e summary.json.

| Original | Timeframes | Resultado técnico |
|---|---|---|
| 13X | M5, M15, H1 | Nenhuma revisão nos buffers rechecados |
| 100 Pips | M5, M15, H1 | Buffers sem revisão; objetos mudam geometria temporal |
| Duck | M5, M15, H1 | 16, 9 e 1 revisões de buffers, respectivamente |
| Gold | M5, M10, M15, H1 | 15, 11, 9 e 2 entradas novas observadas, respectivamente |
| London | H1 | Buffers sem revisão; alterações em objetos |
| Gap | M1, M5, M15 | Nenhum objeto com parâmetros default |

Os períodos são desiguais: 13X e 100 Pips M5 cobrem 04–09/05; demais
testes de ouro cobrem 04–05/05; Gap cobre 21–26/09. Não comparar contagens
como ranking. Model=4 solicita ticks reais; conferir os journals para fallback.
Revisões auxiliares do Duck não demonstram, sozinhas, repaint de entradas.
Caixa Americana não testada economicamente: instrumento WIN não disponível.
Seis testes automatizados de integridade passaram após a atualização.

## Gap Drive: resultado e bloqueio

Defaults, US100.s M1, 21–26/09, Model=4 e CalculateEveryTick=true:
82.200 linhas de buffers, 6.850 fotografias e zero objetos. Defaults continuam
01:00. Cenário hipótese 16:30 (UTC+3 observado, NY 09:30 EDT) não constitui
calendário histórico certificado. Tentativas de carregar parâmetros explícitos
falharam com erro 4002/OnInit; não houve teste válido desse cenário.

Preset original exportado pelo diálogo MT5, sem aplicar ao gráfico:
configs/mt5/vendor_gap_defaults_20260927.set. Corrige informação anterior:
InpBrokerName default é **4XC**, não XXX. Inclui quatro cores além dos oito
inputs funcionais. Mesmo a tentativa de assinatura completa não carregou;
causa ainda não certificada. OverrideGapSession foi bloqueado explicitamente
no registrador para impedir cenários silenciosamente incorretos. Config
pilot27session_gap é registro de tentativa inválida, NÃO um caso aprovado.
Não modificar EX5 nem decompilar para contornar a interface.

O runner agora resolve o agente local pelos dois arquivos novos do RunLabel;
não fixa porta 3000 (visualizadores existentes fizeram MT5 escolher 3001/3002).
Esse problema de localização foi corrigido sem tratar captura antiga como nova.

## Aquisição externa

Obtida semana 14–19/09/2026 de NAS100 Dukascopy M5, bid e ask, 1.311 barras,
100% de correspondência e spread mediano 1,417 em preço. Manifest em
D:/OneB/market-data/dukascopy-validation-20260927/manifest.json.
É CFD de outro feed; não é NQ nem execução HonorPro.

Coleta de NAS100 bid/ask 01/01/2023–11/02/2024 concluída, com 75.909 barras
pareadas e correspondência de 100%, em
D:/OneB/market-data/dukascopy-nas100-2023-2026/normalized/NAS100_M5_2023-01-01_2024-02-11.csv.gz.
Intervalo efetivo: 02/01/2023 23:00–09/02/2024 21:10 UTC. Sem duplicatas,
timestamps inválidos, quotes não finitas, OHLC inválido ou spreads negativos/zero.
Spread mediano na abertura: 3,264 em preço; percentil 95: 3,512.

São 345 datas UTC, incluindo noites de domingo. Pela convenção explícita de
sessão com virada às 18h America/New_York, são 286 rótulos de sessões em dias
úteis. Não é calendário oficial certificado; contém sessões parciais/feriados.
Auditoria reproduzível: scripts/audit_bidask_dataset.py; evidência:
output/vendor_indicator_research/nas100_bidask_year_audit_20260927.json.
SHA256: 18ed241ea06fae9645927048d68460c363fa2689ced131a035e0c97564278f10.
Isso amplia a base de pesquisa, mas não valida a execução no feed HonorPro,
nem substitui NQ/MNQ individuais. Barras bid/ask não reproduzem sequência intrabar.

Para CME individual/BBO, a alternativa oficial consultada é Databento histórico
CME Globex MDP 3.0. Requer conta/API autorizada; não foram criados conta, chave,
assinatura ou gasto. [Serviço histórico](https://databento.com/docs/getting-started/build-first-app?historical=http&live=http).

Conclusão atual: dados bid/ask adicionais adquiridos e Gold corrigido para esta
amostra. Validação econômica dos originais ainda experimental. Não há ranking de
vantagem ou sinais aprovados para negociação.
