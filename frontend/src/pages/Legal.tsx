import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

const CONTACT = import.meta.env.VITE_CONTACT_EMAIL ?? '[definir VITE_CONTACT_EMAIL]';

function LegalPage({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="legal">
      <p>
        <Link to="/">← Início</Link>
      </p>
      <h1>{title}</h1>
      <p className="legal-draft">
        Texto-modelo. Revise com um advogado antes de cobrar clientes (em especial o enquadramento perante a
        CVM e a LGPD).
      </p>
      {children}
    </div>
  );
}

export function Termos() {
  return (
    <LegalPage title="Termos de uso">
      <h2>1. O que é o serviço</h2>
      <p>
        O Monitor NASDAQ é uma ferramenta de monitoramento e informação sobre ativos listados. Ele exibe
        cotações, indicadores, notícias, calendários e métricas de risco, e envia alertas definidos por você.
      </p>
      <h2>2. O que o serviço não é</h2>
      <p>
        O serviço não executa ordens, não custodia valores e não faz recomendação de investimento, análise de
        valores mobiliários ou consultoria. Nenhum conteúdo, inclusive o gerado por inteligência artificial,
        deve ser lido como indicação de compra, venda ou manutenção de um ativo. A decisão e o risco são
        exclusivamente seus.
      </p>
      <h2>3. Dados e disponibilidade</h2>
      <p>
        Os dados vêm de provedores de terceiros, podem ter atraso, falhas ou imprecisões, e o serviço pode
        ficar indisponível. Não garantimos que um alerta será entregue no momento exato nem que será
        entregue. Confira sempre a informação na sua corretora antes de operar.
      </p>
      <h2>4. Resultados</h2>
      <p>
        Desempenho passado, backtests e o registro público de sinais não garantem resultado futuro. Investir
        em renda variável envolve risco de perda, inclusive do capital investido.
      </p>
      <h2>5. Conta, planos e pagamento</h2>
      <p>
        O plano Free é gratuito, com limites de uso. Novos cadastros podem ganhar um período de teste do plano
        Pro. O plano Pro é uma assinatura mensal recorrente, cobrada pelo Stripe, e renova até ser cancelada.
        Você pode cancelar a qualquer momento no portal de assinatura; o acesso Pro segue até o fim do período
        já pago. Valem os direitos previstos na legislação de defesa do consumidor.
      </p>
      <h2>6. Uso aceitável</h2>
      <p>
        Não é permitido usar o serviço para abusar das APIs, compartilhar a conta, revender os dados ou
        tentar acessar contas de terceiros. Podemos suspender contas que violem estes termos.
      </p>
      <h2>7. Encerramento</h2>
      <p>
        Você pode excluir sua conta a qualquer momento em Conta. Podemos encerrar ou alterar o serviço,
        avisando com antecedência razoável quando houver assinatura ativa.
      </p>
      <h2>8. Contato</h2>
      <p>{CONTACT}</p>
    </LegalPage>
  );
}

export function Privacidade() {
  return (
    <LegalPage title="Política de privacidade">
      <h2>1. Dados que coletamos</h2>
      <p>
        Nome de usuário, e-mail, senha (guardada somente como hash), sua watchlist, regras de alerta,
        posições e operações que você registra, alertas disparados e, se você vincular, o identificador do seu
        chat no Telegram. Registramos também a data de aceite dos termos.
      </p>
      <h2>2. Para que usamos</h2>
      <p>
        Para operar o serviço (monitorar seus ativos e entregar alertas), cobrar a assinatura, dar suporte e
        manter a segurança. Não vendemos seus dados.
      </p>
      <h2>3. Com quem compartilhamos</h2>
      <p>
        Stripe, para processar pagamentos (não guardamos número de cartão). Provedores de dados de mercado,
        que recebem apenas os códigos dos ativos. Provedores de inteligência artificial, que recebem o
        contexto da sua watchlist e as suas perguntas quando você usa o assistente, o copiloto ou as análises
        com IA. Telegram, para entregar mensagens ao chat que você vinculou.
      </p>
      <h2>4. Seus direitos (LGPD)</h2>
      <p>
        Você pode confirmar e acessar seus dados, corrigi-los e excluí-los. A exclusão da conta, em Conta,
        apaga seus dados do serviço. Dados de cobrança podem ser mantidos pelo Stripe e por nós pelo prazo
        exigido em lei.
      </p>
      <h2>5. Retenção e segurança</h2>
      <p>
        Mantemos os dados enquanto a conta existir. A comunicação é protegida por HTTPS e as senhas são
        armazenadas com hash.
      </p>
      <h2>6. Contato</h2>
      <p>{CONTACT}</p>
    </LegalPage>
  );
}
