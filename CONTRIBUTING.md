# Contribuindo

1. Não envie `.env`, bancos SQLite, dados de mercado ou chaves de API.
2. Mantenha mudanças pequenas e inclua testes para regras de negócio ou correções.
3. Antes de abrir um pull request, execute `python -m pytest`; no front-end, execute `npm run lint`,
   `npm run build` e `npm run test`.
4. APIs novas precisam de validação Pydantic, autenticação adequada e respostas de erro claras.
5. Não introduza chamadas a provedores externos em testes unitários.
