import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { cadastrar, esperarLogado, uniqueUser } from './helpers';

/** Acessibilidade: falha só em violações sérias/críticas. Um gate em "todas as
 * violações" incluiria avisos menores e seria desligado na primeira semana. */
async function violacoesSerias(page: import('@playwright/test').Page) {
  const { violations } = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze();
  return violations.filter((v) => v.impact === 'serious' || v.impact === 'critical');
}

test('a tela de login não tem violações sérias de acessibilidade', async ({ page }) => {
  await page.goto('/login');
  const serias = await violacoesSerias(page);
  expect(serias.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
});

test('o início não tem violações sérias de acessibilidade', async ({ page }) => {
  await cadastrar(page, uniqueUser('a11y'));
  await esperarLogado(page);
  const serias = await violacoesSerias(page);
  expect(serias.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
});

test('dá para logar só com o teclado', async ({ page }) => {
  await page.goto('/login');
  await page.keyboard.press('Tab');
  await expect(page.getByLabel(/usu[aá]rio/i)).toBeFocused();
});
