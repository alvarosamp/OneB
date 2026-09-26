import { lazy, Suspense, type ComponentType } from 'react';
import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import { ThemeProvider } from './context/ThemeContext';
import { ConfirmProvider } from './components/ConfirmModal';
import { ProtectedRoute, AdminRoute } from './components/ProtectedRoute';
import { AppErrorBoundary } from './components/AppErrorBoundary';
import { AppShell } from './components/terminal/AppShell';
import { RedirectTo } from './components/terminal/RedirectTo';
import { CenteredMessage } from './components/AuthLayout';

function lazyPage(load: () => Promise<object>, name: string) {
  return lazy(async () => ({ default: (await load() as Record<string, ComponentType>)[name]! }));
}

// Público / marketing
const Landing = lazyPage(() => import('./pages/Landing'), 'Landing');
const Login = lazyPage(() => import('./pages/Login'), 'Login');
const Cadastro = lazyPage(() => import('./pages/Cadastro'), 'Cadastro');
const Estrategias = lazyPage(() => import('./pages/Estrategias'), 'Estrategias');
const Comunidade = lazyPage(() => import('./pages/Comunidade'), 'Comunidade');
const Planos = lazyPage(() => import('./pages/Planos'), 'Planos');
const Sobre = lazyPage(() => import('./pages/Sobre'), 'Sobre');
const Aplicacoes = lazyPage(() => import('./pages/Aplicacoes'), 'Aplicacoes');
const Aulas = lazyPage(() => import('./pages/Aulas'), 'Aulas');
const NaoEncontrado = lazyPage(() => import('./pages/NaoEncontrado'), 'NaoEncontrado');

// App logado
const Dashboard = lazyPage(() => import('./pages/Dashboard'), 'Dashboard');
const Mercado = lazyPage(() => import('./pages/Mercado'), 'Mercado');
const Analise = lazyPage(() => import('./pages/Analise'), 'Analise');
const Radar = lazyPage(() => import('./pages/Radar'), 'Radar');
const Watchlist = lazyPage(() => import('./pages/Watchlist'), 'Watchlist');
const Alertas = lazyPage(() => import('./pages/Alertas'), 'Alertas');
const Carteira = lazyPage(() => import('./pages/Carteira'), 'Carteira');
const Assistente = lazyPage(() => import('./pages/Assistente'), 'Assistente');
const AtivoDetalhe = lazyPage(() => import('./pages/AtivoDetalhe'), 'AtivoDetalhe');
const AcademiaHome = lazyPage(() => import('./pages/academia/AcademiaHome'), 'AcademiaHome');
const Trilha = lazyPage(() => import('./pages/academia/Trilha'), 'Trilha');
const Aula = lazyPage(() => import('./pages/academia/Aula'), 'Aula');
const Lives = lazyPage(() => import('./pages/academia/Lives'), 'Lives');
const Configuracoes = lazyPage(() => import('./pages/Configuracoes'), 'Configuracoes');
const Ajuda = lazyPage(() => import('./pages/Ajuda'), 'Ajuda');

export default function App() {
  return (
    <BrowserRouter>
      <AppWithBoundary />
    </BrowserRouter>
  );
}

function AppWithBoundary() {
  const location = useLocation();

  return (
    <ThemeProvider>
      <AuthProvider>
        <ToastProvider>
          <ConfirmProvider>
            {/* A fronteira de erro reinicia por rota, mas sem remontar os providers. */}
            <AppErrorBoundary key={location.pathname}>
              <Suspense fallback={<PageLoading />}>
                <AppRoutes />
              </Suspense>
            </AppErrorBoundary>
          </ConfirmProvider>
        </ToastProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}

/**
 * Mapa de rotas. As rotas antigas continuam válidas via <RedirectTo>, que
 * preserva a query (ver DESIGN.md › Rotas).
 */
function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/aulas" element={<Aulas />} />
      <Route path="/aplicacoes" element={<Aplicacoes />} />
      <Route path="/estrategias" element={<Estrategias />} />
      <Route path="/comunidade" element={<Comunidade />} />
      <Route path="/planos" element={<Planos />} />
      <Route path="/sobre" element={<Sobre />} />
      <Route path="/login" element={<Login />} />
      <Route path="/cadastro" element={<Cadastro />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route path="/ferramenta" element={<Dashboard />} />
          <Route path="/mercado" element={<Mercado />} />
          <Route path="/analise" element={<Analise />} />
          <Route path="/radar" element={<Radar />} />
          <Route path="/watchlist" element={<Watchlist />} />
          <Route path="/alertas" element={<Alertas />} />
          <Route path="/carteira" element={<Carteira />} />
          <Route path="/assistente" element={<Assistente />} />
          <Route path="/ativo/:symbol" element={<AtivoDetalhe />} />
          <Route path="/academia" element={<AcademiaHome />} />
          <Route path="/academia/trilhas/:slug" element={<Trilha />} />
          <Route path="/academia/lives" element={<Lives />} />
          <Route path="/aulas/:slug" element={<Aula />} />
          <Route path="/configuracoes" element={<Configuracoes />} />
          <Route path="/ajuda" element={<Ajuda />} />
        </Route>

        {/* Rotas antigas */}
        <Route path="/inicio" element={<RedirectTo to="/academia" />} />
        <Route path="/aprendizado" element={<RedirectTo to="/academia" />} />
        <Route path="/lives" element={<RedirectTo to="/academia/lives" />} />
        <Route path="/resumo-diario" element={<RedirectTo to="/analise" params={{ tab: 'visao-geral' }} />} />
        <Route path="/analise-matinal" element={<RedirectTo to="/analise" params={{ tab: 'visao-geral' }} />} />
        <Route path="/regime" element={<RedirectTo to="/analise" params={{ tab: 'regime' }} />} />
        <Route path="/mesa-tecnica" element={<RedirectTo to="/analise" params={{ tab: 'tecnica' }} />} />
        <Route path="/inteligencia" element={<RedirectTo to="/radar" />} />
        <Route path="/mesa-ia" element={<RedirectTo to="/assistente" params={{ modo: 'mercado' }} />} />
        <Route path="/copiloto" element={<RedirectTo to="/assistente" params={{ modo: 'ativo' }} />} />
        <Route path="/posicoes" element={<RedirectTo to="/carteira" params={{ tab: 'posicoes' }} />} />
        <Route path="/perfil" element={<RedirectTo to="/carteira" params={{ tab: 'desempenho' }} />} />
        <Route path="/saas" element={<RedirectTo to="/configuracoes" params={{ tab: 'workspace' }} />} />
        <Route path="/como-usar" element={<RedirectTo to="/ajuda" />} />
        <Route path="/operacoes" element={<RedirectTo to="/configuracoes" params={{ tab: 'sistema' }} />} />
        <Route element={<AdminRoute />}>
          <Route path="/usuarios" element={<RedirectTo to="/configuracoes" params={{ tab: 'usuarios' }} />} />
        </Route>
      </Route>
      <Route path="*" element={<NaoEncontrado />} />
    </Routes>
  );
}

function PageLoading() {
  return <CenteredMessage role="status" title="Carregando…" />;
}
