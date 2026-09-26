/**
 * Correção de acentuação para textos livres que chegam do backend sem acento
 * ("Preco acima das medias"). Paliativo: o ideal é o backend devolver o texto
 * já acentuado (listado no relatório como pendência de API).
 */
const WORDS: Record<string, string> = {
  logica: 'lógica', divergencia: 'divergência', comparacao: 'comparação', aceitavel: 'aceitável', observacao: 'observação', proprio: 'próprio', proprios: 'próprios', propria: 'própria', proprias: 'próprias', unica: 'única',
  obrigatoria: 'obrigatória', obrigatorias: 'obrigatórias', saudaveis: 'saudáveis', movel: 'móvel', moveis: 'móveis', politica: 'política', politicas: 'políticas', monetaria: 'monetária', monetarias: 'monetárias', geopolitica: 'geopolítica', energetica: 'energética',
  acao: 'ação', acoes: 'ações', analise: 'análise', analises: 'análises', ate: 'até', atencao: 'atenção',
  basico: 'básico', calendario: 'calendário', cambio: 'câmbio', cenario: 'cenário', codigo: 'código',
  confirmacao: 'confirmação', construcao: 'construção', cotacao: 'cotação', cotacoes: 'cotações',
  decisao: 'decisão', decisoes: 'decisões', diario: 'diário', direcao: 'direção', dolar: 'dólar',
  economico: 'econômico', economicos: 'econômicos', economica: 'econômica', estrategia: 'estratégia',
  estrategias: 'estratégias', execucao: 'execução', exercicio: 'exercício', gestao: 'gestão',
  grafico: 'gráfico', graficos: 'gráficos', historico: 'histórico', indice: 'índice', indices: 'índices',
  informacao: 'informação', inicio: 'início', intermediario: 'intermediário', invalidacao: 'invalidação',
  juros: 'juros', leitura: 'leitura', mao: 'mão', maxima: 'máxima', maximas: 'máximas', media: 'média',
  medias: 'médias', medio: 'médio', minima: 'mínima', minimas: 'mínimas', minimo: 'mínimo', modulo: 'módulo',
  nao: 'não', noticia: 'notícia', noticias: 'notícias', numero: 'número', operacao: 'operação',
  operacoes: 'operações', paciencia: 'paciência', padrao: 'padrão', padroes: 'padrões', periodo: 'período',
  posicao: 'posição', posicoes: 'posições', pratica: 'prática', praticas: 'práticas', preco: 'preço',
  precos: 'preços', pressao: 'pressão', previsao: 'previsão', proximo: 'próximo', proxima: 'próxima',
  proximos: 'próximos', proximas: 'próximas', qualidade: 'qualidade', recomendacao: 'recomendação',
  relatorio: 'relatório', resistencia: 'resistência', revisao: 'revisão', saudavel: 'saudável',
  sessao: 'sessão', simulacao: 'simulação', sinal: 'sinal', tambem: 'também', tecnica: 'técnica',
  tecnicas: 'técnicas', tecnico: 'técnico', tecnicos: 'técnicos', tendencia: 'tendência',
  tendencias: 'tendências', unico: 'único', util: 'útil', vies: 'viés', volatil: 'volátil', ultima: 'última',
  ultimo: 'último', ultimos: 'últimos', ultimas: 'últimas', variacao: 'variação', aprovacao: 'aprovação',
  ja: 'já', sera: 'será', estao: 'estão', voce: 'você', apos: 'após', antecipacao: 'antecipação',
  convicao: 'convicção', correlacao: 'correlação', distancia: 'distância', emocao: 'emoção',
  especulacao: 'especulação', hipotese: 'hipótese', hipoteses: 'hipóteses', critico: 'crítico',
  criticos: 'críticos', critica: 'crítica', estatistica: 'estatística', metrica: 'métrica',
  metricas: 'métricas', memoria: 'memória', neutralizacao: 'neutralização', objetivo: 'objetivo',
  possivel: 'possível', referencia: 'referência', rapido: 'rápido', rapida: 'rápida', sequencia: 'sequência',
  situacao: 'situação', reversao: 'reversão', forca: 'força', evidencia: 'evidência', evidencias: 'evidências',
  disponiveis: 'disponíveis', disponivel: 'disponível', explicaveis: 'explicáveis', testaveis: 'testáveis',
  maximo: 'máximo', horarios: 'horários', horario: 'horário', pregao: 'pregão', comissoes: 'comissões',
  protecao: 'proteção', evolucao: 'evolução', auditavel: 'auditável', diaria: 'diária', diarias: 'diárias',
  basica: 'básica', facil: 'fácil', dificil: 'difícil', conteudo: 'conteúdo', video: 'vídeo', videos: 'vídeos',
  nivel: 'nível', niveis: 'níveis', indicadores: 'indicadores', psicologia: 'psicologia',
  hipotetico: 'hipotético', liquidos: 'líquidos', confiaveis: 'confiáveis', confiavel: 'confiável',
  aluno: 'aluno', analitico: 'analítico', eletronico: 'eletrônico', acompanhamento: 'acompanhamento',
  subjetividade: 'subjetividade', apoio: 'apoio', fantasia: 'fantasia', estimativa: 'estimativa',
  objetivos: 'objetivos', ruido: 'ruído', piloto: 'piloto', rapidamente: 'rapidamente',
  sequencias: 'sequências', ciclo: 'ciclo', construtiva: 'construtiva', construtivo: 'construtivo',
  expectativa: 'expectativa', petroleo: 'petróleo', liquidez: 'liquidez', agressao: 'agressão',
};

function matchCase(source: string, target: string): string {
  if (source === source.toUpperCase() && source.length > 1) return target.toUpperCase();
  if (source[0] === source[0].toUpperCase()) return target[0].toUpperCase() + target.slice(1);
  return target;
}

const RE = new RegExp(`\\b(${Object.keys(WORDS).join('|')})\\b`, 'gi');

export function ptBR(text: string | null | undefined): string {
  if (!text) return '';
  return text
    .replace(RE, (w) => {
      const fixed = WORDS[w.toLowerCase()];
      return fixed ? matchCase(w, fixed) : w;
    })
    // Decimal com ponto vindo do backend ("RSI em 52.84") vira vírgula; datas e horas não são afetadas.
    .replace(/(^|[^\d.])(\d+)\.(\d+)(?![\d.])/g, '$1$2,$3');
}
