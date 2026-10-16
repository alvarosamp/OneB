# Indicador OneB Risco para o MetaTrader 5

Mostra no gráfico o que o OneB mede, sem precisar de internet e **sem enviar ordens**:

- **quanto o mercado deve mexer hoje** (previsão aprovada em teste pré-registrado, volfc_v1), com a faixa de 80% e quanto já andou;
- **das 10:30 de Brasília até o fechamento de Nova York**, quanto o preço ainda deve andar (Nasdaq e ouro, aprovados no teste sessfc_v1), com a faixa de 80% e quanto já andou;
- linhas pontilhadas de **até onde o dia costuma ir** a partir da máxima ou da mínima de hoje;
- **stop de 1,5 ATR de 1 hora** e os alvos de 1R, 2R e 3R, com a **chance real** de cada um (2023–2026, com spread);
- o **lote** para o seu saldo e risco, ou o aviso de que nem o lote mínimo cabe;
- a **qualidade da hora atual** e o próximo **CPI, payroll ou FOMC** (calendário do próprio MT5).

Não é sinal de compra ou venda: nenhuma regra de direção passou nos testes do OneB.

## Instalar

1. No MT5: **Arquivo › Abrir pasta de dados**.
2. Copie `OneB_Risco.ex5` (ou `OneB_Risco.mq5`) para `MQL5\Indicators`.
3. No MT5, na janela **Navegador**, clique com o botão direito em **Indicadores › Atualizar**.
4. Arraste **OneB_Risco** para o gráfico do US100.s, US500.s, XAUUSD.s ou EURUSD.s.
5. Nas configurações: saldo (0 = saldo da conta), risco por operação (%) e stop em ATR (a chance medida só existe para 1,5).

Funciona com os símbolos da HonorPro e com nomes parecidos de outras corretoras (US100, NAS100, USTEC, XAUUSD, GOLD, US500, EURUSD).

## Atualizar

Quando a pesquisa mudar, gere de novo e recompile:

```
python scripts/build_mt5_indicator.py
"C:\Program Files\Honor Pro MT5 Terminal\MetaEditor64.exe" /compile:"mt5\OneB_Risco.mq5"
```

`OneB_Risco.template.mq5` é o código; `OneB_Risco.mq5` é gerado (com os números da pesquisa embutidos) e não deve ser editado à mão.
