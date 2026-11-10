from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.auth import get_current_user
from app.db import get_db
from app.models import Course, CourseModule, DecisionJournal, Lesson, LessonProgress, TradeSetup, User
from app.schemas import (
    CertificateStatusOut,
    CourseOut,
    CourseSummaryOut,
    LearningRecommendationOut,
    LearningStateOut,
    LessonOut,
    ModuleOut,
)

router = APIRouter(prefix="/api/lms", tags=["lms"], dependencies=[Depends(get_current_user)])

REQUIRED_SIMULATIONS_FOR_CERTIFICATE = 3


def _completed_lesson_ids(db: Session, user_id: int) -> set[int]:
    rows = db.query(LessonProgress.lesson_id).filter(LessonProgress.user_id == user_id).all()
    return {row[0] for row in rows}


def _lesson_material(title: str) -> dict:
    return _LESSON_MATERIAL.get(
        title,
        {
            "summary": "Estude o conceito, conecte com a mesa tecnica e registre uma regra objetiva antes de operar.",
            "checklist": [
                "Entendi o conceito principal.",
                "Consigo explicar quando usar.",
                "Consigo explicar quando nao usar.",
                "Registrei uma invalidacao objetiva.",
            ],
            "exercise": "Abra um ativo da watchlist, escreva a tese, o gatilho e o motivo que faria voce nao operar.",
            "required": True,
        },
    )


def _lesson_out(lesson: Lesson, completed_ids: set[int]) -> LessonOut:
    material = _lesson_material(lesson.title)
    return LessonOut(
        id=lesson.id,
        title=lesson.title,
        description=lesson.description,
        video_url=lesson.video_url,
        duration_minutes=lesson.duration_minutes,
        order=lesson.order,
        completed=lesson.id in completed_ids,
        summary=material["summary"],
        checklist=material["checklist"],
        exercise=material["exercise"],
        required=material["required"],
    )


def _course_summaries(db: Session, user_id: int) -> list[CourseSummaryOut]:
    courses = (
        db.query(Course)
        .filter(Course.published.is_(True))
        .options(selectinload(Course.modules).selectinload(CourseModule.lessons))
        .order_by(Course.order)
        .all()
    )
    completed_ids = _completed_lesson_ids(db, user_id)
    out: list[CourseSummaryOut] = []
    for course in courses:
        lessons = [lesson for module in course.modules for lesson in module.lessons]
        out.append(
            CourseSummaryOut(
                id=course.id,
                slug=course.slug,
                title=course.title,
                description=course.description,
                order=course.order,
                lesson_count=len(lessons),
                completed_count=sum(1 for lesson in lessons if lesson.id in completed_ids),
            )
        )
    return out


def _find_lesson_target(db: Session, lesson_title: str) -> tuple[Course, Lesson] | None:
    row = (
        db.query(Course, Lesson)
        .join(CourseModule, CourseModule.course_id == Course.id)
        .join(Lesson, Lesson.module_id == CourseModule.id)
        .filter(Lesson.title == lesson_title, Course.published.is_(True))
        .order_by(Course.order, CourseModule.order, Lesson.order)
        .first()
    )
    return row


def _first_incomplete_required(db: Session, user_id: int) -> tuple[Course, Lesson] | None:
    completed_ids = _completed_lesson_ids(db, user_id)
    rows = (
        db.query(Course, Lesson)
        .join(CourseModule, CourseModule.course_id == Course.id)
        .join(Lesson, Lesson.module_id == CourseModule.id)
        .filter(Course.published.is_(True))
        .order_by(Course.order, CourseModule.order, Lesson.order)
        .all()
    )
    for course, lesson in rows:
        if lesson.id not in completed_ids and _lesson_material(lesson.title)["required"]:
            return course, lesson
    return None


def _next_recommendation(db: Session, user: User) -> LearningRecommendationOut | None:
    latest_decision = (
        db.query(DecisionJournal)
        .filter(DecisionJournal.user_id == user.id)
        .order_by(DecisionJournal.created_at.desc())
        .first()
    )

    target_title = ""
    reason = ""
    gap = ""
    if latest_decision is not None:
        if not latest_decision.invalidation.strip():
            target_title = "Tese, gatilho e invalidacao"
            gap = "invalidation_missing"
            reason = "Sua decisao mais recente nao tinha invalidacao clara."
        elif not latest_decision.risk_notes.strip():
            target_title = "Definindo seu risco maximo"
            gap = "risk_missing"
            reason = "Sua decisao mais recente nao tinha nota de risco."
        elif not latest_decision.trigger.strip():
            target_title = "Tese, gatilho e invalidacao"
            gap = "trigger_missing"
            reason = "Sua decisao mais recente nao tinha gatilho objetivo."

    target = _find_lesson_target(db, target_title) if target_title else None
    if target is None:
        target = _first_incomplete_required(db, user.id)
        if target is None:
            return None
        reason = "Continue a primeira aula obrigatoria ainda nao concluida."
        gap = "next_required_lesson"

    course, lesson = target
    return LearningRecommendationOut(
        reason=reason,
        course_slug=course.slug,
        course_title=course.title,
        lesson_id=lesson.id,
        lesson_title=lesson.title,
        gap=gap,
    )


def _certificate_status(db: Session, user: User) -> CertificateStatusOut:
    completed_ids = _completed_lesson_ids(db, user.id)
    lessons = (
        db.query(Lesson)
        .join(CourseModule, Lesson.module_id == CourseModule.id)
        .join(Course, CourseModule.course_id == Course.id)
        .filter(Course.published.is_(True))
        .all()
    )
    required_lessons = [lesson for lesson in lessons if _lesson_material(lesson.title)["required"]]
    completed_required = sum(1 for lesson in required_lessons if lesson.id in completed_ids)
    simulation_count = db.query(TradeSetup).filter(TradeSetup.user_id == user.id).count()
    progress_pct = round((completed_required / len(required_lessons)) * 100) if required_lessons else 0
    enough_lessons = completed_required >= len(required_lessons) and bool(required_lessons)
    enough_simulations = simulation_count >= REQUIRED_SIMULATIONS_FOR_CERTIFICATE

    if not enough_lessons:
        next_requirement = "Concluir todas as aulas obrigatorias."
    elif not enough_simulations:
        missing = REQUIRED_SIMULATIONS_FOR_CERTIFICATE - simulation_count
        next_requirement = f"Registrar mais {missing} setup(s) praticos na Mesa Tecnica."
    else:
        next_requirement = "Certificado liberado."

    return CertificateStatusOut(
        eligible=enough_lessons and enough_simulations,
        progress_pct=progress_pct,
        completed_required_lessons=completed_required,
        required_lessons=len(required_lessons),
        completed_simulations=simulation_count,
        required_simulations=REQUIRED_SIMULATIONS_FOR_CERTIFICATE,
        next_requirement=next_requirement,
    )


@router.get("/courses", response_model=list[CourseSummaryOut])
def list_courses(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _course_summaries(db, user.id)


@router.get("/learning-state", response_model=LearningStateOut)
def learning_state(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return LearningStateOut(
        courses=_course_summaries(db, user.id),
        recommendation=_next_recommendation(db, user),
        certificate=_certificate_status(db, user),
    )


@router.get("/courses/{slug}", response_model=CourseOut)
def get_course(slug: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    course = (
        db.query(Course)
        .filter(Course.slug == slug, Course.published.is_(True))
        .options(selectinload(Course.modules).selectinload(CourseModule.lessons))
        .first()
    )
    if course is None:
        raise HTTPException(status_code=404, detail="Curso nao encontrado.")

    completed_ids = _completed_lesson_ids(db, user.id)
    modules_out = [
        ModuleOut(
            id=module.id,
            title=module.title,
            order=module.order,
            lessons=[_lesson_out(lesson, completed_ids) for lesson in module.lessons],
        )
        for module in course.modules
    ]
    lessons_flat = [lesson for module in modules_out for lesson in module.lessons]
    return CourseOut(
        id=course.id,
        slug=course.slug,
        title=course.title,
        description=course.description,
        order=course.order,
        lesson_count=len(lessons_flat),
        completed_count=sum(1 for lesson in lessons_flat if lesson.completed),
        modules=modules_out,
    )


@router.post("/lessons/{lesson_id}/complete", status_code=204)
def complete_lesson(lesson_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if lesson is None:
        raise HTTPException(status_code=404, detail="Aula nao encontrada.")
    existing = (
        db.query(LessonProgress)
        .filter(LessonProgress.user_id == user.id, LessonProgress.lesson_id == lesson_id)
        .first()
    )
    if existing is None:
        db.add(LessonProgress(user_id=user.id, lesson_id=lesson_id))
        db.commit()


@router.delete("/lessons/{lesson_id}/complete", status_code=204)
def uncomplete_lesson(lesson_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.query(LessonProgress).filter(
        LessonProgress.user_id == user.id, LessonProgress.lesson_id == lesson_id
    ).delete()
    db.commit()


_COURSES_SEED = [
    (
        "fundamentos",
        "Fundamentos do mercado americano",
        "Base para entender NASDAQ, ETFs, indices, custos, horarios, dados e apoio a decisao.",
        [
            (
                "Mercado americano sem fantasia",
                [
                    ("Como funciona a NASDAQ", "Estrutura do mercado, horarios de pregao, indices e ativos acompanhados.", 12),
                    ("Ordens, corretoras e custos", "Tipos de ordem, spread, comissoes, slippage e limites dos dados.", 14),
                    ("O que o OneB pode e nao pode fazer", "Apoio a decisao, alertas, simulacao e diferenca para recomendacao.", 10),
                ],
            ),
            (
                "Rotina inicial",
                [
                    ("Montando sua watchlist piloto", "Escolha poucos ativos, defina objetivo e evite excesso de ruido.", 12),
                    ("Leitura diaria antes da abertura", "Como olhar indices, noticias, calendario e contexto antes de setup.", 15),
                ],
            ),
        ],
    ),
    (
        "analise-tecnica-avancada",
        "Analise tecnica e price action",
        "Contexto, candles, medias, momentum, volatilidade e setups simples, testaveis e explicaveis.",
        [
            (
                "Contexto antes do setup",
                [
                    ("Candles e price action", "Como ler candles sem transformar todo movimento em sinal.", 15),
                    ("Tendencia, faixa e reversao", "Como identificar regime antes de escolher setup.", 16),
                    ("Suporte, resistencia e zonas", "Como marcar niveis relevantes e evitar subjetividade demais.", 14),
                ],
            ),
            (
                "Indicadores como evidencia",
                [
                    ("Medias, RSI e MACD sem excesso de sinal", "Uso pratico dos indicadores ja disponiveis.", 18),
                    ("Volume e forca do movimento", "Volume relativo para validar ou descartar rompimento.", 13),
                    ("ATR, Bollinger e volatilidade", "Como adaptar stop, alvo e expectativa ao tamanho do movimento.", 16),
                ],
            ),
            (
                "Pratica guiada",
                [
                    ("Montando um setup na Mesa Tecnica", "Passo a passo com tese, entrada, stop, alvo e invalidacao.", 20),
                ],
            ),
        ],
    ),
    (
        "gestao-de-risco-e-psicologia",
        "Gestao de risco e psicologia",
        "Protecao de capital, tamanho de posicao, disciplina e decisao consciente de nao operar.",
        [
            (
                "Risco por operacao",
                [
                    ("Definindo seu risco maximo", "Percentual de risco por trade, por dia e por carteira.", 12),
                    ("Tamanho de posicao e stop", "Como calcular tamanho antes de pensar no alvo.", 14),
                    ("Circuit breakers pessoais", "Regras para parar apos sequencia de perdas ou perda diaria.", 10),
                ],
            ),
            (
                "Psicologia operacional",
                [
                    ("Lidando com FOMO e overtrading", "Gatilhos emocionais comuns e como neutraliza-los.", 15),
                    ("Quando aceitar o NO_TRADE", "Como transformar espera em decisao profissional.", 12),
                ],
            ),
        ],
    ),
    (
        "processo-diario-e-revisao",
        "Processo, diario e revisao",
        "Rotina para registrar decisoes, revisar erros e transformar operacao em aprendizado mensuravel.",
        [
            (
                "Diario de decisao",
                [
                    ("Journaling de decisoes", "Registrar tese, gatilho, invalidacao, risco e resultado.", 13),
                    ("Tese, gatilho e invalidacao", "Como escrever uma decisao auditavel antes de operar.", 16),
                    ("Revisao de falso positivo", "Como aprender com sinais que pareciam bons e falharam.", 14),
                ],
            ),
            (
                "Rotina semanal",
                [
                    ("Checklist semanal da Mesa", "Revisar aulas, sinais bloqueados, score e drawdown simulado.", 12),
                    ("Plano de evolucao individual", "Escolher a proxima aula com base no erro mais recente.", 11),
                ],
            ),
        ],
    ),
]


_LESSON_MATERIAL: dict[str, dict] = {
    "Como funciona a NASDAQ": {
        "summary": "A NASDAQ e um mercado eletronico com horarios, liquidez, indices e ativos diferentes. O aluno aprende o que esta observando e quando o dado pode estar atrasado.",
        "checklist": ["Diferencio acao, ETF e indice.", "Sei o horario regular do mercado.", "Entendo atraso em dados gratuitos.", "Escolhi poucos ativos para o piloto."],
        "exercise": "Monte uma watchlist com 5 ativos americanos e escreva por que cada um merece acompanhamento.",
        "required": True,
    },
    "Ordens, corretoras e custos": {
        "summary": "Toda operacao carrega spread, taxa, slippage e risco de execucao. Um setup so e bom se continuar fazendo sentido depois dos custos.",
        "checklist": ["Entendi ordem a mercado, limitada e stop.", "Consigo explicar spread e slippage.", "Nao avalio setup sem custo estimado.", "Sei que o OneB nao envia ordens no MVP."],
        "exercise": "Pegue um setup hipotetico e estime quanto spread e slippage reduziriam o resultado.",
        "required": True,
    },
    "O que o OneB pode e nao pode fazer": {
        "summary": "O produto monitora, organiza evidencias, alerta e educa. Ele nao promete acerto, nao substitui julgamento e nao deve ser tratado como recomendacao financeira.",
        "checklist": ["Entendi apoio a decisao versus recomendacao.", "Sei que NO_TRADE e valido.", "Sei que a IA explica, mas nao aprova risco.", "Valido qualquer sinal antes de operar fora do sistema."],
        "exercise": "Escreva tres situacoes em que o sistema deve responder NO_TRADE.",
        "required": True,
    },
    "Montando sua watchlist piloto": {
        "summary": "Uma watchlist pequena reduz ruido e melhora revisao. O piloto deve comecar com ativos liquidos e objetivos claros.",
        "checklist": ["Minha watchlist tem poucos ativos.", "Cada ativo tem motivo de acompanhamento.", "Evitei ativos sem liquidez ou dados confiaveis.", "Defini alertas que fariam sentido."],
        "exercise": "Crie sua watchlist piloto e registre uma regra simples para um ativo.",
        "required": True,
    },
    "Leitura diaria antes da abertura": {
        "summary": "Antes de buscar setup, o aluno olha contexto: indices, macro, noticias, calendario e risco do dia.",
        "checklist": ["Olhei indices principais.", "Chequei eventos economicos.", "Verifiquei noticias relevantes.", "Defini se o dia pede cautela."],
        "exercise": "Escreva uma analise matinal com 3 riscos e 3 pontos de atencao.",
        "required": True,
    },
    "Candles e price action": {
        "summary": "Candles mostram disputa entre compradores e vendedores, mas precisam de contexto. Isolados, viram ruido.",
        "checklist": ["Identifiquei candle no contexto.", "Nao usei candle isolado como sinal final.", "Marquei nivel relevante.", "Defini invalidacao antes da entrada."],
        "exercise": "Escolha um ativo e descreva candle atual, contexto e invalidacao.",
        "required": True,
    },
    "Tendencia, faixa e reversao": {
        "summary": "Cada regime pede uma logica diferente. Rompimento, pullback e reversao exigem filtros proprios.",
        "checklist": ["Classifiquei o regime.", "Evitei rompimento fraco em lateralidade.", "Escolhi setup coerente.", "Defini quando esperar."],
        "exercise": "Classifique 3 ativos da watchlist por regime e escreva o setup permitido para cada um.",
        "required": True,
    },
    "Suporte, resistencia e zonas": {
        "summary": "Niveis sao regioes de decisao, nao linhas magicas. Eles ajudam a planejar risco, alvo e invalidacao.",
        "checklist": ["Marquei zonas recentes.", "Usei pivots ou swing levels.", "Evitei criar niveis demais.", "Conectei nivel com stop ou alvo."],
        "exercise": "Marque suporte, resistencia, entrada e invalidacao para um setup planejado.",
        "required": True,
    },
    "Medias, RSI e MACD sem excesso de sinal": {
        "summary": "Indicadores confirmam uma tese, nao substituem leitura. Medias leem tendencia, RSI le momentum e MACD ajuda a ver virada ou forca.",
        "checklist": ["Usei poucos indicadores.", "Expliquei o papel de cada indicador.", "Procurei contradicoes.", "Retornei NO_TRADE quando a leitura ficou confusa."],
        "exercise": "Monte uma regra com media, RSI ou MACD e escreva quando ela deve falhar.",
        "required": True,
    },
    "Volume e forca do movimento": {
        "summary": "Volume relativo ajuda a diferenciar movimento com participacao de mercado de oscilacao fraca.",
        "checklist": ["Comparei volume atual com media.", "Evitei rompimento sem participacao.", "Chequei nivel relevante.", "Nao usei volume sozinho como entrada."],
        "exercise": "Encontre um candle com volume acima da media e explique se confirma ou contradiz o setup.",
        "required": True,
    },
    "ATR, Bollinger e volatilidade": {
        "summary": "Volatilidade define tamanho de stop, distancia de alvo e se o mercado esta comprimido ou expandido.",
        "checklist": ["Usei ATR para dimensionar stop.", "Reconheci compressao e expansao.", "Evitei alvo irrealista.", "Ajustei tamanho da posicao ao risco."],
        "exercise": "Compare dois ativos com volatilidades diferentes e ajuste stop e tamanho para cada um.",
        "required": True,
    },
    "Montando um setup na Mesa Tecnica": {
        "summary": "Um setup completo tem contexto, gatilho, confirmacao, invalidacao, stop, alvo e criterio de nao operar.",
        "checklist": ["Contexto definido.", "Gatilho objetivo definido.", "Stop e alvo calculados.", "Criterio de NO_TRADE escrito."],
        "exercise": "Crie um setup na Mesa Tecnica com tese, entrada, stop, alvo e invalidacao.",
        "required": True,
    },
    "Definindo seu risco maximo": {
        "summary": "Risco maximo vem antes de setup. O aluno define limite por operacao, por dia e por carteira.",
        "checklist": ["Defini risco por operacao.", "Defini perda diaria maxima.", "Defini quando parar.", "Aceito reduzir tamanho quando a incerteza aumenta."],
        "exercise": "Calcule o risco maximo em dolares para 0,5%, 1% e 2% de uma carteira ficticia.",
        "required": True,
    },
    "Tamanho de posicao e stop": {
        "summary": "Tamanho de posicao nasce da distancia ate o stop e do risco aceito. Sem stop, nao existe tamanho responsavel.",
        "checklist": ["Stop definido antes da quantidade.", "Quantidade calculada pelo risco.", "Risco/retorno avaliado.", "Operacao descartada se o stop ficar incoerente."],
        "exercise": "Use o simulador da aula para calcular quantidade, risco planejado e R/R.",
        "required": True,
    },
    "Circuit breakers pessoais": {
        "summary": "Circuit breaker pessoal impede que emocao transforme erro pequeno em dano grande.",
        "checklist": ["Defini limite de perda diaria.", "Defini limite de trades por dia.", "Defini regra apos sequencia de perdas.", "Escrevi acao obrigatoria quando disparar."],
        "exercise": "Escreva seu protocolo de parada para um dia ruim.",
        "required": True,
    },
    "Lidando com FOMO e overtrading": {
        "summary": "FOMO e overtrading aparecem quando o aluno troca processo por urgencia. A rotina desacelera a decisao.",
        "checklist": ["Identifico urgencia emocional.", "Uso checklist antes da entrada.", "Aceito perder movimento sem plano.", "Registro quando ignorei regra."],
        "exercise": "Descreva uma situacao de FOMO e qual regra teria bloqueado a operacao.",
        "required": True,
    },
    "Quando aceitar o NO_TRADE": {
        "summary": "NO_TRADE protege capital quando dados, regime, risco ou evidencia estao ruins. Esperar faz parte do metodo.",
        "checklist": ["Sei citar motivos objetivos de NO_TRADE.", "Nao forco trade em dado conflitante.", "Nao opero sem invalidacao.", "Registro a decisao de esperar."],
        "exercise": "Registre uma decisao no diario explicando por que voce nao operaria.",
        "required": True,
    },
    "Journaling de decisoes": {
        "summary": "O diario transforma decisao em material de aprendizado: tese, gatilho, invalidacao, risco e resultado.",
        "checklist": ["Registrei tese.", "Registrei gatilho.", "Registrei invalidacao.", "Registrei risco e prazo."],
        "exercise": "Crie uma entrada no Diario de Decisao com todos os campos preenchidos.",
        "required": True,
    },
    "Tese, gatilho e invalidacao": {
        "summary": "Sem invalidacao, a tese nao pode ser auditada. O aluno precisa saber exatamente o que provaria que estava errado.",
        "checklist": ["A tese e especifica.", "O gatilho e observavel.", "A invalidacao e objetiva.", "O prazo da ideia esta claro."],
        "exercise": "Pegue uma decisao recente e reescreva tese, gatilho e invalidacao em frases objetivas.",
        "required": True,
    },
    "Revisao de falso positivo": {
        "summary": "Falso positivo ensina quando a evidencia parecia boa, mas o mercado nao confirmou. O foco e ajustar processo.",
        "checklist": ["Comparei confianca e resultado.", "Busquei sinal contraditorio ignorado.", "Identifiquei mudanca de regime.", "Atualizei regra ou checklist."],
        "exercise": "Revise uma recomendacao registrada e escreva o que teria bloqueado ou reduzido tamanho.",
        "required": True,
    },
    "Checklist semanal da Mesa": {
        "summary": "A revisao semanal conecta estudo, sinais, bloqueios, acerto, drawdown e proximas aulas.",
        "checklist": ["Revisei aulas concluidas.", "Revisei sinais bloqueados.", "Revisei acerto 5d.", "Escolhi uma lacuna para estudar."],
        "exercise": "Preencha a revisao semanal usando as metricas da Fase 1.",
        "required": True,
    },
    "Plano de evolucao individual": {
        "summary": "A proxima aula nasce do erro operacional: sem invalidacao, sem risco, FOMO, excesso de sinal ou leitura ruim de regime.",
        "checklist": ["Identifiquei erro frequente.", "Escolhi aula ligada ao erro.", "Defini exercicio para corrigir.", "Vou medir se o erro diminuiu."],
        "exercise": "Escolha uma lacuna pessoal e monte um plano de estudo de 7 dias.",
        "required": True,
    },
}


def seed_default_courses(db: Session) -> None:
    for course_order, (slug, title, description, modules_data) in enumerate(_COURSES_SEED, start=1):
        course = db.query(Course).filter(Course.slug == slug).first()
        if course is None:
            course = Course(slug=slug, title=title, description=description, order=course_order, published=True)
            db.add(course)
            db.flush()
        else:
            course.title = title
            course.description = description
            course.order = course_order
            course.published = True

        for module_order, (module_title, lessons) in enumerate(modules_data, start=1):
            module = (
                db.query(CourseModule)
                .filter(CourseModule.course_id == course.id, CourseModule.title == module_title)
                .first()
            )
            if module is None:
                module = CourseModule(course_id=course.id, title=module_title, order=module_order)
                db.add(module)
                db.flush()
            else:
                module.order = module_order

            for lesson_order, (lesson_title, lesson_description, duration) in enumerate(lessons, start=1):
                lesson = db.query(Lesson).filter(Lesson.module_id == module.id, Lesson.title == lesson_title).first()
                if lesson is None:
                    db.add(
                        Lesson(
                            module_id=module.id,
                            title=lesson_title,
                            description=lesson_description,
                            video_url="",
                            duration_minutes=duration,
                            order=lesson_order,
                        )
                    )
                else:
                    lesson.description = lesson_description
                    lesson.duration_minutes = duration
                    lesson.order = lesson_order

    db.commit()
