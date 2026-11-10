import { expect, test } from '@playwright/test';
import { API_URL, cadastrar, entrar, esperarLogado, uniqueUser } from './helpers';

test.describe('autenticação', () => {
  test('cadastro cria conta comum e entra no sistema', async ({ page }) => {
    const user = uniqueUser('cadastro');
    await cadastrar(page, user);
    await esperarLogado(page);
  });

  test('cadastro público nunca concede admin', async ({ page, request }) => {
    // Regressão do achado P0: a primeira conta criada virava administradora, então quem
    // chegasse primeiro num deploy novo ganhava controle total.
    const user = uniqueUser('naoadmin');
    const res = await request.post(`${API_URL}/api/auth/cadastro`, { data: user });
    expect(res.status()).toBe(201);
    expect((await res.json()).user.is_admin).toBe(false);

    await entrar(page, user);
    await esperarLogado(page);
    // Rota de admin não pode responder para conta comum.
    const usuarios = await request.get(`${API_URL}/api/auth/usuarios`);
    expect([401, 403]).toContain(usuarios.status());
  });

  test('o access token nunca é gravado em localStorage', async ({ page }) => {
    // Regressão do achado P0: o JWT de 7 dias ficava em localStorage, legível por
    // qualquer XSS. Agora vive em memória, e a sessão persiste via cookie httpOnly.
    const user = uniqueUser('storage');
    await cadastrar(page, user);
    await esperarLogado(page);

    const storage = await page.evaluate(() => ({ ...localStorage }));
    expect(JSON.stringify(storage)).not.toMatch(/eyJ/); // nenhum JWT em storage
    expect(Object.keys(storage)).not.toContain('oneb_market_token');
  });

  test('o cookie de sessão é httpOnly e não é legível por JavaScript', async ({ page, context }) => {
    const user = uniqueUser('cookie');
    await cadastrar(page, user);
    await esperarLogado(page);

    const cookies = await context.cookies();
    const refresh = cookies.find((c) => c.name.includes('refresh'));
    expect(refresh, 'o cookie de refresh deveria existir').toBeTruthy();
    expect(refresh!.httpOnly).toBe(true);

    const visivelParaJs = await page.evaluate(() => document.cookie);
    expect(visivelParaJs).not.toContain(refresh!.value);
  });

  test('a sessão sobrevive ao reload da página', async ({ page }) => {
    // O access token morre no reload (vive em memória); quem reconstrói a sessão é o
    // cookie httpOnly via /api/auth/refresh.
    const user = uniqueUser('reload');
    await cadastrar(page, user);
    await esperarLogado(page);

    await page.reload();
    await expect(page).toHaveURL(/\/ferramenta/);
    await expect(page.getByRole('link', { name: /login/i })).toHaveCount(0);
  });

  test('senha errada mostra a mensagem do servidor e não entra', async ({ page }) => {
    const user = uniqueUser('senha');
    await cadastrar(page, user);
    await esperarLogado(page);

    await page.context().clearCookies();
    await entrar(page, { username: user.username, password: 'senha-errada-9999' });

    await expect(page.getByText(/inv[aá]lid/i)).toBeVisible({ timeout: 10_000 });
    await expect(page).toHaveURL(/\/login/);
  });

  test('sessão expirada leva de volta ao login', async ({ page, context }) => {
    const user = uniqueUser('expira');
    await cadastrar(page, user);
    await esperarLogado(page);

    // Derruba a sessão como o servidor faria: sem cookie de refresh, a renovação
    // silenciosa falha e o app precisa voltar para o login em vez de travar numa tela vazia.
    await context.clearCookies();
    await page.reload();
    await expect(page).toHaveURL(/\/login/, { timeout: 15_000 });
  });

  test('logout revoga a sessão no servidor', async ({ page, context }) => {
    const user = uniqueUser('logout');
    await cadastrar(page, user);
    await esperarLogado(page);

    await page.getByRole('button', { name: /menu da conta/i }).click();
    await page.getByRole('menuitem', { name: /^sair$/i }).click();
    await expect(page).toHaveURL(/\/login/, { timeout: 15_000 });

    // O refresh não pode mais valer: a família inteira foi revogada.
    const cookies = await context.cookies();
    const refresh = cookies.find((c) => c.name.includes('refresh'));
    expect(refresh?.value ?? '').toBe('');
  });

  test('rota protegida sem sessão redireciona para o login', async ({ page }) => {
    await page.goto('/ferramenta');
    await expect(page).toHaveURL(/\/login/, { timeout: 15_000 });
  });
});
