export const navLinks = [
  { href: '/aulas', label: 'Aprender' },
  { href: '/aplicacoes', label: 'Ferramentas' },
  { href: '/estrategias', label: 'Estratégias' },
  { href: '/planos', label: 'Planos' },
  { href: '/sobre', label: 'A OneB' },
];

export const courseTracks = [
  {
    slug: 'fundamentos',
    title: 'Fundamentos do mercado americano',
    level: 'Iniciante',
    status: 'Disponível',
    theme: 'Base',
  },
  {
    slug: 'analise-tecnica-avancada',
    title: 'Análise técnica e price action',
    level: 'Intermediário',
    status: 'Disponível',
    theme: 'Técnica',
  },
  {
    slug: 'gestao-de-risco-e-psicologia',
    title: 'Gestão de risco e psicologia',
    level: 'Essencial',
    status: 'Disponível',
    theme: 'Risco',
  },
  {
    slug: 'processo-diario-e-revisao',
    title: 'Processo, diário e revisão',
    level: 'Prática',
    status: 'Disponível',
    theme: 'Método',
  },
  {
    slug: 'analise-tecnica-avancada',
    title: 'Leitura de regime e contexto',
    level: 'Intermediário',
    status: 'Disponível',
    theme: 'Macro',
  },
  {
    slug: 'mesa-ia-aplicada',
    title: 'Mesa IA aplicada',
    level: 'Avançado',
    status: 'Plano avançado',
    theme: 'IA',
  },
];

export const plans = [
  {
    name: 'Escola',
    description: 'Para aprender o método OneB e praticar com simulação guiada.',
    price: 'R$ 49',
    featured: false,
    benefits: [
      'Aulas e trilhas essenciais',
      'Checklists de estudo e risco',
      'Simulação guiada antes da operação',
      'Lives e revisões da comunidade',
    ],
  },
  {
    name: 'Escola + Terminal',
    description: 'O MVP principal: educação, watchlist, alertas e apoio a decisão.',
    price: 'R$ 97',
    featured: true,
    benefits: [
      'Tudo do plano Escola',
      'Watchlist com alertas configuráveis',
      'Resumo diário e contexto de mercado',
      'Posições manuais, P&L e risco',
      'Assistente IA explicando dados coletados',
    ],
  },
  {
    name: 'Mesa Guiada',
    description: 'Para alunos que querem acompanhamento mais próximo e rotina de revisão.',
    price: 'R$ 197',
    featured: false,
    benefits: [
      'Tudo do Escola + Terminal',
      'Lives práticas com revisão de cenários',
      'Trilhas avançadas de estratégia',
      'Roteiro de evolução individual',
    ],
  },
];

export const applications = [
  {
    key: 'school',
    category: 'Aprendizado',
    title: 'Trilhas de aprendizado',
    description: 'Aulas, checklists e prática guiada para formar método antes da decisão.',
    href: '/aulas',
    metrics: ['Trilhas práticas', 'Checklists', 'Exercícios'],
  },
  {
    key: 'terminal',
    category: 'Monitoramento',
    title: 'Watchlist e alertas',
    description: 'Monitoramento de ativos, regras configuráveis, histórico e resumo diário.',
    href: '/ferramenta',
    metrics: ['Watchlist', 'Alertas', 'Contexto'],
  },
  {
    key: 'risk',
    category: 'Decisão',
    title: 'Decisão protegida',
    description: 'Leitura de qualidade dos dados, risco e motivos claros para operar ou esperar.',
    href: '/mesa-ia',
    metrics: ['NO_TRADE', 'Risco', 'Diário'],
  },
];

export const strategies = [
  {
    category: 'Método',
    title: 'Contexto antes do setup',
    description: 'Aprenda a ler regime, tendência e invalidação antes de procurar entrada.',
    lessons: 12,
    level: 'Iniciante',
  },
  {
    category: 'Risco',
    title: 'Tamanho de posição',
    description: 'Transforme risco por operação em uma regra objetiva e repetível.',
    lessons: 8,
    level: 'Essencial',
  },
  {
    category: 'Técnica',
    title: 'Price Action com confirmação',
    description: 'Use gatilho, volume e zonas importantes sem depender de promessa de acerto.',
    lessons: 14,
    level: 'Intermediário',
  },
  {
    category: 'Revisão',
    title: 'Diário operacional',
    description: 'Registre decisões, motivos de espera e aprendizados para evoluir com evidência.',
    lessons: 6,
    level: 'Prática',
  },
];

export const resultStats = [
  { value: '5-10', label: 'usuarios piloto para validar o MVP' },
  { value: '1 rotina', label: 'estudar, monitorar, alertar e revisar' },
  { value: '0 ordens', label: 'sem execução automatica no MVP' },
];
