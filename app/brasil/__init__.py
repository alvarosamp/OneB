"""Seção Brasil: educação e simulação de investimentos (não é corretora nem consultoria).

- rates: Selic, CDI e IPCA oficiais do Banco Central (SGS), com valor de reserva.
- products: o que é cada classe de investimento, risco, liquidez, garantia e imposto.
- simulator: perfil, divisão por CLASSE (nunca por ativo específico) e projeção
  líquida de IR e custódia, comparada à poupança.
- market: retrato da B3 (índices, ETFs, ações e FIIs mais negociados) e o
  comparativo histórico Ibovespa x CDI x IPCA.

A recomendação personalizada de valor mobiliário específico exige registro na CVM
(Resoluções CVM 19 e 20). Por isso o simulador fala em classes ("Tesouro Selic",
"ETF de ações brasileiras"), explica o porquê e nunca diz "compre a ação X".
"""
