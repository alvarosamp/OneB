# Contribuindo

1. Não envie `.env`, bancos SQLite, dados de mercado ou chaves de API.
2. Mantenha mudanças pequenas e inclua testes para regras de negócio ou correções.
3. Antes de abrir um pull request, execute `python -m pytest`; no front-end, execute `npm run lint`,
   `npm run build` e `npm run test`.
4. APIs novas precisam de validação Pydantic, autenticação adequada e respostas de erro claras.
5. Não introduza chamadas a provedores externos em testes unitários.

## Banco e migrations

Mudou `app/models.py`? Gere a migration e verifique que ela sobe e desce:

```bash
alembic revision --autogenerate -m "descricao curta"
alembic upgrade head
alembic downgrade -1 && alembic upgrade head
```

## Checks que o CI roda

```bash
ruff check app tests scripts            # lint (versão pinada no workflow)
pytest -q --cov=app --cov-fail-under=55 # testes + cobertura mínima
mypy --ignore-missing-imports app/auth.py app/config.py app/security.py app/routers/auth.py
bandit -r app -ll                       # análise estática de segurança
pip-audit -r requirements.txt           # CVEs nas dependências

cd frontend
npm run lint
npx tsc --noEmit -p tsconfig.app.json
npm run test                            # unitários (vitest)
npm run test:e2e                        # E2E (Playwright) — precisa da API em :8000
npm run build
```

## Segurança

Vulnerabilidades **não** vão para issues públicas — ver [`SECURITY.md`](SECURITY.md).
