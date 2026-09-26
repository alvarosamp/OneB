/**
 * Access token em memória — de propósito.
 *
 * Antes o JWT (válido por 7 dias) ficava em localStorage, então qualquer XSS em
 * qualquer dependência do SPA conseguia ler uma credencial de uma semana e não
 * havia como revogá-la. Agora o access token dura minutos e vive só nesta variável
 * de módulo: ele morre no reload da página, e a sessão é reconstruída pelo refresh
 * token, que está num cookie httpOnly que o JavaScript não consegue ler.
 */
let accessToken: string | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function clearAccessToken(): void {
  accessToken = null;
}
