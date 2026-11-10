from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "oneb_market_guia_projeto.pdf"


def styles():
    base = getSampleStyleSheet()
    base.add(
        ParagraphStyle(
            name="CoverTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=28,
            leading=34,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#111827"),
            spaceAfter=18,
        )
    )
    base.add(
        ParagraphStyle(
            name="CoverSub",
            parent=base["Normal"],
            fontSize=12,
            leading=18,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#4b5563"),
        )
    )
    base.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#111827"),
            spaceBefore=10,
            spaceAfter=8,
        )
    )
    base.add(
        ParagraphStyle(
            name="Small",
            parent=base["Normal"],
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#4b5563"),
        )
    )
    base["BodyText"].fontSize = 10
    base["BodyText"].leading = 14
    return base


def bullet(text: str, style):
    return Paragraph(f"- {text}", style)


def table(data, widths):
    cell_style = ParagraphStyle(
        name="Cell",
        fontName="Helvetica",
        fontSize=8.2,
        leading=10.2,
        textColor=colors.black,
    )
    head_style = ParagraphStyle(
        name="CellHead",
        parent=cell_style,
        fontName="Helvetica-Bold",
        textColor=colors.white,
    )
    wrapped = []
    for row_index, row in enumerate(data):
        row_style = head_style if row_index == 0 else cell_style
        wrapped.append([Paragraph(escape(str(cell)), row_style) for cell in row])

    t = Table(wrapped, colWidths=widths, hAlign="LEFT", repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("LEADING", (0, 0), (-1, -1), 10.5),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return t


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#6b7280"))
    canvas.drawString(1.6 * cm, 1.1 * cm, "OneB Market - documentacao do projeto")
    canvas.drawRightString(19.4 * cm, 1.1 * cm, f"Pagina {doc.page}")
    canvas.restoreState()


def build():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    s = styles()
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        rightMargin=1.6 * cm,
        leftMargin=1.6 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
        title="OneB Market - Guia do Projeto",
    )

    story = []
    story.append(Spacer(1, 5 * cm))
    story.append(Paragraph("OneB Market", s["CoverTitle"]))
    story.append(
        Paragraph(
            "Guia do projeto, aplicacoes presentes e fluxo operacional para monitoramento, "
            "analise assistida por IA, risco e diario inteligente.",
            s["CoverSub"],
        )
    )
    story.append(Spacer(1, 0.5 * cm))
    story.append(
        Paragraph(
            "Versao local: FastAPI + React + Docker Compose. O sistema nao executa ordens "
            "e nao constitui recomendacao de investimento.",
            s["CoverSub"],
        )
    )
    story.append(PageBreak())

    story.append(Paragraph("1. Visao Geral", s["SectionTitle"]))
    for item in [
        "A OneB Market e uma plataforma de apoio a decisao para acompanhar ativos, alertas, noticias e contexto macro.",
        "O foco nao e apenas exibir graficos. O produto organiza dados e oferece interpretacao explicavel.",
        "A aplicacao combina dashboard, regras, noticias, chatbot, copiloto multiagente, perfil do trader e relatorios.",
        "O usuario continua responsavel por validar qualquer decisao e executar ordens fora do sistema.",
    ]:
        story.append(bullet(item, s["BodyText"]))
    story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph("2. Arquitetura", s["SectionTitle"]))
    story.append(
        table(
            [
                ["Camada", "Tecnologia", "Papel"],
                ["Backend", "FastAPI, SQLAlchemy, APScheduler", "API REST, banco SQLite, jobs de coleta e regras."],
                ["Frontend", "React, TypeScript, Vite", "SPA com dashboard, telas operacionais e UX do copiloto."],
                ["Dados", "Finnhub, yfinance, FMP", "Cotacoes, historico, noticias, earnings, calendario economico, dolar e ouro."],
                ["IA", "Groq, Gemini ou Anthropic", "Explicacao de dados, narrativa, chatbot e contexto em alertas."],
                ["Infra local", "Docker Compose", "Sobe backend e frontend juntos para desenvolvimento e uso local."],
            ],
            [3.0 * cm, 5.0 * cm, 8.2 * cm],
        )
    )
    story.append(PageBreak())

    story.append(Paragraph("3. Aplicacoes Presentes", s["SectionTitle"]))
    story.append(
        table(
            [
                ["Aplicacao", "O que faz", "Quando usar"],
                ["Dashboard", "Radar de ativos, KPIs, dolar, ouro, macro, noticias, alertas e posicoes.", "Primeira tela da rotina diaria."],
                ["Watchlist e Regras", "Cadastro de ativos e regras compostas com backtest.", "Quando quiser monitorar um ativo ou criar alertas."],
                ["Mercado", "Noticias por ativo, noticias globais, calendario economico e earnings.", "Para entender contexto externo antes de agir."],
                ["Alertas", "Historico e filtros dos sinais disparados.", "Para auditar o que aconteceu e quando."],
                ["Posicoes", "Registro manual de compras e vendas, P&L e historico.", "Para medir exposicao e resultado."],
                ["Copiloto", "Multiagentes votam e explicam tecnico, noticias, macro, risco e perfil.", "Antes de planejar uma operacao manual."],
                ["Perfil", "Diario inteligente, taxa de acerto, profit factor, horarios, ativos e licoes.", "Para aprender com o proprio comportamento."],
                ["Assistente IA", "Chatbot sobre dados coletados pelo sistema.", "Para perguntar e resumir contexto."],
                ["Usuarios", "Gestao de usuarios administradores.", "Para controlar acesso."],
            ],
            [3.0 * cm, 8.0 * cm, 5.2 * cm],
        )
    )
    story.append(PageBreak())

    story.append(Paragraph("4. Copiloto de Trading", s["SectionTitle"]))
    for item in [
        "O Copiloto e o principal diferencial: ele transforma dados em uma decisao explicavel.",
        "O usuario informa ativo, capital, risco maximo e pergunta. O sistema retorna vies, confianca e votos.",
        "Agentes atuais: Tecnico, Noticias, Macro, Risco e Perfil.",
        "A resposta inclui tese principal, tese contraria, plano de risco, simulacao historica e padroes detectados.",
        "Nao ha broker integrado. Nao existe compra automatica.",
    ]:
        story.append(bullet(item, s["BodyText"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(
        table(
            [
                ["Agente", "Entrada analisada", "Saida"],
                ["Tecnico", "Historico, EMAs, RSI, MACD, volume e variacao.", "Voto tecnico e evidencias."],
                ["Noticias", "Noticias por ativo e alertas recentes.", "Sentimento operacional simplificado."],
                ["Macro", "Noticias globais e calendario economico.", "Contexto de risco para o mercado."],
                ["Risco", "Capital, risco maximo, volatilidade e posicao existente.", "Tamanho sugerido e stop aproximado."],
                ["Perfil", "Transacoes manuais e diario inteligente.", "Alertas sobre padroes pessoais."],
            ],
            [3.0 * cm, 8.0 * cm, 5.2 * cm],
        )
    )
    story.append(PageBreak())

    story.append(Paragraph("5. Perfil e Diario Inteligente", s["SectionTitle"]))
    for item in [
        "O perfil aprende a partir das operacoes fechadas registradas manualmente.",
        "Calcula P&L fechado, taxa de acerto, ganho medio, perda media, expectativa, profit factor e tempo medio em posicao.",
        "Agrupa resultados por ativo, horario de entrada e estilo: intraday, swing curto e swing longo.",
        "O diario gera uma licao por operacao, apontando saida cedo, perda rapida, stop ruim ou necessidade de revisar tese.",
        "Quanto mais o usuario registrar entradas e saidas, mais util o Perfil fica para o Copiloto.",
    ]:
        story.append(bullet(item, s["BodyText"]))

    story.append(Paragraph("6. Fontes de Dados", s["SectionTitle"]))
    story.append(
        table(
            [
                ["Fonte", "Uso no sistema", "Observacao"],
                ["Finnhub", "Cotacao atual, noticias por ativo, noticias globais e earnings.", "Exige API key; free tier tem limites."],
                ["yfinance", "Historico OHLCV, indicadores, USD/BRL e ouro GC=F.", "Fonte gratuita, pode ter atraso ou instabilidade."],
                ["FMP", "Calendario economico.", "Opcional; sem key o sistema roda sem essa secao."],
                ["LLM", "Explicacao, chatbot e narrativa.", "Nao cria dados de mercado; interpreta dados coletados."],
            ],
            [3.0 * cm, 8.0 * cm, 5.2 * cm],
        )
    )
    story.append(PageBreak())

    story.append(Paragraph("7. Fluxo Operacional Recomendado", s["SectionTitle"]))
    for item in [
        "Abrir o Dashboard e verificar qualidade dos dados, dolar, ouro, noticias globais e eventos criticos.",
        "Usar o radar para priorizar quais ativos investigar primeiro.",
        "Abrir o ativo e validar grafico, indicadores e noticias recentes.",
        "Rodar o Copiloto com capital e risco maximo antes de planejar uma entrada.",
        "Ler a tese contraria e o plano de risco antes de executar qualquer ordem fora do sistema.",
        "Registrar compras e vendas em Posicoes.",
        "Revisar Perfil semanalmente para identificar erros recorrentes e vantagens pessoais.",
    ]:
        story.append(bullet(item, s["BodyText"]))

    story.append(Paragraph("8. Setup e Docker", s["SectionTitle"]))
    for item in [
        "Rodar localmente com docker compose up -d --build.",
        "Frontend: http://localhost:5173.",
        "Backend: http://localhost:8000.",
        "Variaveis essenciais: FINNHUB_API_KEY, SECRET_KEY, FRONTEND_ORIGIN e VITE_API_URL.",
        "Variaveis opcionais recomendadas: FMP_API_KEY, LLM_PROVIDER, GROQ_API_KEY ou GEMINI_API_KEY, TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID.",
    ]:
        story.append(bullet(item, s["BodyText"]))
    story.append(Spacer(1, 0.4 * cm))
    story.append(
        Paragraph(
            "Aviso: a plataforma e uma ferramenta de apoio a decisao. Dados podem ter atraso, fontes gratuitas podem falhar e nenhuma resposta deve ser tratada como recomendacao garantida.",
            s["Small"],
        )
    )

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return OUTPUT


if __name__ == "__main__":
    print(build())
