import { expect, test } from '@playwright/test';
import { cadastrar, esperarLogado, uniqueUser } from './helpers';

/** A UI precisa distinguir falhas: "API fora do ar" e "quota estourada" não podem
 * aparecer como uma tela vazia, que o usuário lê como "não tenho nada cadastrado". */
test.describe('degradação de provider', () => {
  test('API indisponível mostra erro de conexão, não tela vazia', async ({ page }) => {
    const user = uniqueUser('offline');
    await cadastrar(page, user);
    await esperarLogado(page);

    await page.route('**/api/watchlist*', (route) => route.abort('failed'));
    await page.goto('/watchlist');

    await expect(page.getByText(/n[aã]o foi poss[ií]vel|erro|falha/i).first()).toBeVisible({
      timeout: 15_000,
    });
  });

  test('quota 429 do provider é comunicada ao usuário', async ({ page }) => {
    const user = uniqueUser('quota');
    await cadastrar(page, user);
    await esperarLogado(page);

    await page.route('**/api/watchlist*', (route) =>
      route.fulfill({
        status: 429,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Limite de requisições do provedor atingido.' }),
      }),
    );
    await page.goto('/watchlist');

    await expect(page.getByText(/limite|429|requisi/i).first()).toBeVisible({ timeout: 15_000 });
  });
});
