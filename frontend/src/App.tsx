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

function Layout({ children }: { children: ReactNode }) {
  return (
    <>
      <Navbar />
      <main>{children}</main>
      <footer className="disclaimer">
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
      <AuthProvider>
        <ToastProvider>
          <ConfirmProvider>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/cadastro" element={<Cadastro />} />

              <Route element={<ProtectedRoute />}>
                <Route
                  path="/"
                  element={
                    <Layout>
                      <Dashboard />
                    </Layout>
                  }
                />
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
                      <AnaliseMatinal />
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
                      <Assistente />
                    </Layout>
                  }
                />
                <Route
                  path="/copiloto"
                  element={
                    <Layout>
                      <Copiloto />
                    </Layout>
                  }
                />
                <Route
                  path="/pesquisa"
                  element={
                    <Layout>
                      <Pesquisa />
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
