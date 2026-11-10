# Contrato de dados intradiarios — Nasdaq e ouro

## Arquivo minimo

Um CSV por instrumento com barras consecutivas de 1, 5 ou 15 minutos:

```csv
timestamp,open,high,low,close,volume
2026-01-02 09:30:00,21000.00,21002.25,20998.75,21001.50,1842
```

Exportacoes MT5 com `DATE,TIME,OPEN,HIGH,LOW,CLOSE,TICK_VOLUME` tambem sao aceitas.
O fuso de timestamps sem offset deve ser informado por `--source-timezone`. Nao
converter o fuso do servidor manualmente sem registrar a regra usada.

Quando o arquivo de NQ/MNQ possui barras M1, o pipeline deriva e testa 1, 5,
10 e 15 minutos. Para ouro, deriva e testa o timeframe principal de 10 minutos.
Timeframes agregados usam apenas barras inferiores ja encerradas.

## Instrumentos aceitos

- `NQ`: E-mini Nasdaq-100, USD 20 por ponto, tick 0,25.
- `MNQ`: Micro E-mini Nasdaq-100, USD 2 por ponto, tick 0,25.
- `NAS100`: CFD/indice tecnico equivalente; valor do ponto depende da corretora e nao constitui evidencia de NQ.
- `GC`: Gold, 100 oncas, tick USD 0,10 por onca.
- `MGC`: Micro Gold, 10 oncas, tick USD 0,10 por onca.
- `XAUUSD`: especificacao depende da corretora; os valores padrao sao placeholders e precisam ser substituidos.

Comissao, spread e slippage no arquivo de pesquisa sao hipoteses explicitas, nao
tarifas universais. Calibre-as com o relatorio da corretora antes de qualquer
paper trading.

## Cobertura recomendada

- Minimo para o pipeline produzir ranking: 250 sessoes.
- Recomendado: 3 a 5 anos completos.
- Manter pregao regular e overnight; nao fornecer apenas barras onde houve sinal.
- Preservar volume zero, gaps e trocas de contrato para auditoria.
- Para futuros continuos, fornecer identificador do contrato e regra de rollover
  em arquivo separado. Ajustes retroativos de preco devem ser documentados.

## Execucao

```powershell
.\.venv\Scripts\python.exe scripts\intraday_setup_research.py `
  --market NQ=data\intraday\NQ_5m.csv `
  --market GC=data\intraday\GC_5m.csv `
  --source-timezone America/New_York
```

Sem os arquivos, o resultado esperado e `BLOCKED`. Isso e um controle de
qualidade e impede que dados diarios ou artificiais sejam apresentados como
validacao intradiaria.
