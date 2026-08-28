import { lazy, Suspense, type ComponentType, type ReactNode } from 'react';
import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import { ThemeProvider } from './context/ThemeContext';
import { ConfirmProvider } from './components/ConfirmModal';
import { Navbar } from './components/Navbar';
import { Sidebar } from './components/Sidebar';
import { ProtectedRoute, AdminRoute } from './components/ProtectedRoute';
import { AppErrorBoundary } from './components/AppErrorBoundary';

function lazyPage(load: () => Promise<object>, name: string) {
  return lazy(async () => ({ default: (await load() as Record<string, ComponentType>)[name]! }));
}

const Login = lazyPage(() => import('./pages/Login'), 'Login');
const Cadastro = lazyPage(() => import('./pages/Cadastro'), 'Cadastro');
const Landing = lazyPage(() => import('./pages/Landing'), 'Landing');
const Estrategias = lazyPage(() => import('./pages/Estrategias'), 'Estrategias');
const Comunidade = lazyPage(() => import('./pages/Comunidade'), 'Comunidade');
const Planos = lazyPage(() => import('./pages/Planos'), 'Planos');
const Sobre = lazyPage(() => import('./pages/Sobre'), 'Sobre');
const Aplicacoes = lazyPage(() => import('./pages/Aplicacoes'), 'Aplicacoes');
const Hub = lazyPage(() => import('./pages/Hub'), 'Hub');
const Aulas = lazyPage(() => import('./pages/Aulas'), 'Aulas');
const Aprendizado = lazyPage(() => import('./pages/Aprendizado'), 'Aprendizado');
const CursoDetalhe = lazyPage(() => import('./pages/CursoDetalhe'), 'CursoDetalhe');
const Lives = lazyPage(() => import('./pages/Lives'), 'Lives');
const Dashboard = lazyPage(() => import('./pages/Dashboard'), 'Dashboard');
const Watchlist = lazyPage(() => import('./pages/Watchlist'), 'Watchlist');
const Mercado = lazyPage(() => import('./pages/Mercado'), 'Mercado');
const AnaliseMatinal = lazyPage(() => import('./pages/AnaliseMatinal'), 'AnaliseMatinal');
const Alertas = lazyPage(() => import('./pages/Alertas'), 'Alertas');
const Posicoes = lazyPage(() => import('./pages/Posicoes'), 'Posicoes');
const Assistente = lazyPage(() => import('./pages/Assistente'), 'Assistente');
const Usuarios = lazyPage(() => import('./pages/Usuarios'), 'Usuarios');
const AtivoDetalhe = lazyPage(() => import('./pages/AtivoDetalhe'), 'AtivoDetalhe');
const ComoUsar = lazyPage(() => import('./pages/ComoUsar'), 'ComoUsar');
const Copiloto = lazyPage(() => import('./pages/Copiloto'), 'Copiloto');
const Perfil = lazyPage(() => import('./pages/Perfil'), 'Perfil');
const Saas = lazyPage(() => import('./pages/Saas'), 'Saas');
const Inteligencia = lazyPage(() => import('./pages/Inteligencia'), 'Inteligencia');
const Operacoes = lazyPage(() => import('./pages/Operacoes'), 'Operacoes');
const MesaTecnica = lazyPage(() => import('./pages/MesaTecnica'), 'MesaTecnica');
const MesaIA = lazyPage(() => import('./pages/MesaIA'), 'MesaIA');
const Regime = lazyPage(() => import('./pages/Regime'), 'Regime');
const ResumoDiario = lazyPage(() => import('./pages/ResumoDiario'), 'ResumoDiario');
const NaoEncontrado = lazyPage(() => import('./pages/NaoEncontrado'), 'NaoEncontrado');

function Layout({ children }: { children: ReactNode }) {
  return (
    <>
      <Navbar />
      <main className="academy-layout">{children}</main>
      <footer className="disclaimer app-disclaimer">
        Ferramenta apenas de monitoramento e sugestão. Não executa ordens e não constitui
        recomendação de investimento. Dados podem ter atraso. Valide qualquer sinal antes de
        decidir.
      </footer>
    </>
  );
}

function ToolLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <Navbar />
      <div className="app-shell">
        <Sidebar />
        <main className="app-shell-content terminal-layout">{children}</main>
      </div>
      <footer className="disclaimer app-disclaimer terminal-disclaimer">
        Ferramenta apenas de monitoramento e sugestão. Não executa ordens e não constitui
        recomendação de investimento. Dados podem ter atraso. Valide qualquer sinal antes de
        decidir.
      </footer>
    </>
  );
}

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
    <AppErrorBoundary key={location.pathname}>
      <ThemeProvider>
        <AuthProvider>
          <ToastProvider>
            <ConfirmProvider>
              <Suspense fallback={<PageLoading />}>
                <Routes>
                <Route
                  path="/"
                  element={<Landing />}
                />
                <Route path="/aulas" element={<Aulas />} />
                <Route path="/aplicacoes" element={<Aplicacoes />} />
                <Route path="/estrategias" element={<Estrategias />} />
                <Route path="/comunidade" element={<Comunidade />} />
                <Route path="/planos" element={<Planos />} />
                <Route path="/sobre" element={<Sobre />} />
                <Route path="/login" element={<Login />} />
                <Route path="/cadastro" element={<Cadastro />} />

                <Route element={<ProtectedRoute />}>
                  <Route
                    path="/inicio"
                    element={
                      <Layout>
                        <Hub />
                      </Layout>
                    }
                  />
                  <Route
                    path="/aprendizado"
                    element={
                      <Layout>
                        <Aprendizado />
                      </Layout>
                    }
                  />
                  <Route
                    path="/aulas/:slug"
                    element={
                      <Layout>
                        <CursoDetalhe />
                      </Layout>
                    }
                  />
                  <Route
                    path="/lives"
                    element={
                      <Layout>
                        <Lives />
                      </Layout>
                    }
                  />
                  <Route
                    path="/perfil"
                    element={
                      <Layout>
                        <Perfil />
                      </Layout>
                    }
                  />

                  <Route
                    path="/ferramenta"
                    element={
                      <ToolLayout>
                        <Dashboard />
                      </ToolLayout>
                    }
                  />
                  <Route
                    path="/watchlist"
                    element={
                      <ToolLayout>
                        <Watchlist />
                      </ToolLayout>
                    }
                  />
                  <Route
                    path="/mercado"
                    element={
                      <ToolLayout>
                        <Mercado />
                      </ToolLayout>
                    }
                  />
                  <Route
                    path="/analise-matinal"
                    element={
                      <ToolLayout>
                        <AnaliseMatinal />
                      </ToolLayout>
                    }
                  />
                  <Route
                    path="/alertas"
                    element={
                      <ToolLayout>
                        <Alertas />
                      </ToolLayout>
                    }
                  />
                  <Route
                    path="/posicoes"
                    element={
                      <ToolLayout>
                        <Posicoes />
                      </ToolLayout>
                    }
                  />
                  <Route
                    path="/assistente"
                    element={
                      <ToolLayout>
                        <Assistente />
                      </ToolLayout>
                    }
                  />
                  <Route
                    path="/copiloto"
                    element={
                      <ToolLayout>
                        <Copiloto />
                      </ToolLayout>
                    }
                  />
                  <Route
                    path="/saas"
                    element={
                      <ToolLayout>
                        <Saas />
                      </ToolLayout>
                    }
                  />
                  <Route
                    path="/inteligencia"
                    element={
                      <ToolLayout>
                        <Inteligencia />
                      </ToolLayout>
                    }
                  />
                  <Route
                    path="/operacoes"
                    element={
                      <ToolLayout>
                        <Operacoes />
                      </ToolLayout>
                    }
                  />
                  <Route
                    path="/resumo-diario"
                    element={
                      <ToolLayout>
                        <ResumoDiario />
                      </ToolLayout>
                    }
                  />
                  <Route
                    path="/mesa-ia"
                    element={
                      <ToolLayout>
                        <MesaIA />
                      </ToolLayout>
                    }
                  />
                  <Route
                    path="/mesa-tecnica"
                    element={
                      <ToolLayout>
                        <MesaTecnica />
                      </ToolLayout>
                    }
                  />
                  <Route
                    path="/regime"
                    element={
                      <ToolLayout>
                        <Regime />
                      </ToolLayout>
                    }
                  />
                  <Route
                    path="/ativo/:symbol"
                    element={
                      <ToolLayout>
                        <AtivoDetalhe />
                      </ToolLayout>
                    }
                  />
                  <Route
                    path="/como-usar"
                    element={
                      <ToolLayout>
                        <ComoUsar />
                      </ToolLayout>
                    }
                  />

                  <Route element={<AdminRoute />}>
                    <Route
                      path="/usuarios"
                      element={
                        <ToolLayout>
                          <Usuarios />
                        </ToolLayout>
                      }
                    />
                  </Route>
                </Route>
                <Route path="*" element={<NaoEncontrado />} />
                </Routes>
              </Suspense>
            </ConfirmProvider>
          </ToastProvider>
        </AuthProvider>
      </ThemeProvider>
    </AppErrorBoundary>
  );
}

function PageLoading() {
  return <main className="app-loading-state" aria-live="polite">Carregando ambiente OneB…</main>;
}
