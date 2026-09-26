import { expect, type Page } from '@playwright/test';

export const API_URL = process.env.VITE_API_URL ?? 'http://localhost:8000';

/** Usuário novo a cada execução: a API guarda estado, então reaproveitar nome quebraria
 * o cadastro na segunda rodada (e mascararia falhas com "usuário já existe"). */
export function uniqueUser(prefix = 'e2e') {
  return { username: `${prefix}-${Date.now()}-${Math.floor(Math.random() * 1e4)}`, password: 'senha-e2e-12345' };
}

export async function cadastrar(page: Page, user: { username: string; password: string }) {
  await page.goto('/cadastro');
  await page.getByLabel(/usu[aá]rio/i).fill(user.username);
  await page.getByLabel(/^senha$/i).fill(user.password);
  await page.getByLabel(/confirmar senha/i).fill(user.password);
  await page.getByRole('button', { name: /criar conta/i }).click();
}

export async function entrar(page: Page, user: { username: string; password: string }) {
  await page.goto('/login');
  await page.getByLabel(/usu[aá]rio/i).fill(user.username);
  await page.getByLabel(/senha/i).fill(user.password);
  await page.getByRole('button', { name: /^entrar$/i }).click();
}

export async function esperarLogado(page: Page) {
  await expect(page).toHaveURL(/\/ferramenta/, { timeout: 15_000 });
}
