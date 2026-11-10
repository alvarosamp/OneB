import type { ReactNode } from 'react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import { ConfirmProvider } from './components/ConfirmModal';
import { Navbar } from './components/Navbar';
import { ProtectedRoute, AdminRoute } from './components/ProtectedRoute';
import { Login } from './pages/Login';
import { Cadastro } from './pages/Cadastro';
import { Dashboard } from './pages/Dashboard';
import { Watchlist } from './pages/Watchlist';
import { Mercado } from './pages/Mercado';
import { AnaliseMatinal } from './pages/AnaliseMatinal';
import { Alertas } from './pages/Alertas';
import { Posicoes } from './pages/Posicoes';
import { Assistente } from './pages/Assistente';
import { Usuarios } from './pages/Usuarios';
import { AtivoDetalhe } from './pages/AtivoDetalhe';
import { ComoUsar } from './pages/ComoUsar';
import { Copiloto } from './pages/Copiloto';
import { Perfil } from './pages/Perfil';
import { Pesquisa } from './pages/Pesquisa';
import { Analise } from './pages/Analise';
import { Publico } from './pages/Publico';
import { Landing } from './pages/Landing';
import { Planos } from './pages/Planos';
import { Conta } from './pages/Conta';
import { Privacidade, Termos } from './pages/Legal';
import { ProGate } from './components/ProGate';
import { PlanBanner } from './components/PlanBanner';
import { useAuth } from './context/AuthContext';

function Layout({ children }: { children: ReactNode }) {
  return (
    <>
      <Navbar />
      <PlanBanner />
      <main>{children}</main>
      <footer className="disclaimer">
        Ferramenta apenas de monitoramento e sugestão. Não executa ordens e não constitui
        recomendação de investimento. Dados podem ter atraso. Valide qualquer sinal antes de
        decidir.
      </footer>
    </>
  );
}

/** Visitante vê a página de venda; quem está logado cai direto no painel. */
function Home() {
  const { user, loading } = useAuth();
  if (loading) {
    return <p className="muted" style={{ padding: '1.5rem' }}>Carregando...</p>;
  }
  if (!user) return <Landing />;
  return (
    <Layout>
      <Dashboard />
    </Layout>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <ConfirmProvider>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/cadastro" element={<Cadastro />} />
              <Route path="/publico" element={<Publico />} />
              <Route path="/termos" element={<Termos />} />
              <Route path="/privacidade" element={<Privacidade />} />
              <Route path="/" element={<Home />} />

              <Route element={<ProtectedRoute />}>
                <Route
                  path="/watchlist"
                  element={
                    <Layout>
                      <Watchlist />
                    </Layout>
                  }
                />
                <Route
                  path="/mercado"
                  element={
                    <Layout>
                      <Mercado />
                    </Layout>
                  }
                />
                <Route
                  path="/analise-matinal"
                  element={
                    <Layout>
                      <ProGate feature="Análise matinal">
                        <AnaliseMatinal />
                      </ProGate>
                    </Layout>
                  }
                />
                <Route
                  path="/alertas"
                  element={
                    <Layout>
                      <Alertas />
                    </Layout>
                  }
                />
                <Route
                  path="/posicoes"
                  element={
                    <Layout>
                      <Posicoes />
                    </Layout>
                  }
                />
                <Route
                  path="/assistente"
                  element={
                    <Layout>
                      <ProGate feature="Assistente IA">
                        <Assistente />
                      </ProGate>
                    </Layout>
                  }
                />
                <Route
                  path="/copiloto"
                  element={
                    <Layout>
                      <ProGate feature="Copiloto">
                        <Copiloto />
                      </ProGate>
                    </Layout>
                  }
                />
                <Route
                  path="/analise"
                  element={
                    <Layout>
                      <ProGate feature="Painel de risco">
                        <Analise />
                      </ProGate>
                    </Layout>
                  }
                />
                <Route
                  path="/pesquisa"
                  element={
                    <Layout>
                      <ProGate feature="Pesquisa">
                        <Pesquisa />
                      </ProGate>
                    </Layout>
                  }
                />
                <Route
                  path="/planos"
                  element={
                    <Layout>
                      <Planos />
                    </Layout>
                  }
                />
                <Route
                  path="/conta"
                  element={
                    <Layout>
                      <Conta />
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
                  path="/ativo/:symbol"
                  element={
                    <Layout>
                      <AtivoDetalhe />
                    </Layout>
                  }
                />
                <Route
                  path="/como-usar"
                  element={
                    <Layout>
                      <ComoUsar />
                    </Layout>
                  }
                />

                <Route element={<AdminRoute />}>
                  <Route
                    path="/usuarios"
                    element={
                      <Layout>
                        <Usuarios />
                      </Layout>
                    }
                  />
                </Route>
              </Route>
            </Routes>
          </ConfirmProvider>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
