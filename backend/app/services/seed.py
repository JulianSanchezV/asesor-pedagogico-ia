from sqlalchemy.orm import Session
from app.auth import hash_password
from app.config import get_settings
from app.models import AISettingsModel, Cohort, Lab, RubricVersion, User

settings = get_settings()


def _std_levels(e_desc: str, s_desc: str, a_desc: str, i_desc: str) -> list[dict]:
    return [
        {"level": "excelente", "label": "Excelente (4.5 - 5.0)", "score_ratio": 1.0, "descriptor": e_desc},
        {"level": "sobresaliente", "label": "Sobresaliente (3.8 - 4.4)", "score_ratio": 0.85, "descriptor": s_desc},
        {"level": "aceptable", "label": "Aceptable (3.0 - 3.7)", "score_ratio": 0.68, "descriptor": a_desc},
        {"level": "insuficiente", "label": "Insuficiente (< 3.0)", "score_ratio": 0.35, "descriptor": i_desc},
    ]


def get_default_labs_spec(c1_id: int, c2_id: int) -> list[tuple]:
    return [
        (
            c1_id,
            "LAB-1.2",
            "Laboratorio 2: Mzls Resiliente",
            "Diseño y desarrollo de una solución apoyada en Inteligencia Artificial orientada a la resiliencia urbana y territorial de Manizales, integrando análisis del problema, modelado técnico y documentación de evidencias.",
            [
                "Analizar una problemática real de resiliencia en Manizales y estructurar su solución con apoyo de IA.",
                "Implementar un prototipo funcional con código verificable y buenas prácticas de ingeniería.",
                "Documentar metodología, decisiones técnicas, resultados y reflexiones en el informe del laboratorio.",
            ],
            ["IA Aplicada a Resiliencia Urbana", "Análisis de Problemas con IA", "Ingeniería de Software Aumentada"],
            [
                {
                    "id": "c1",
                    "name": "Comprensión del problema y solución propuesta (Mzls Resiliente)",
                    "competency": "Formulación de soluciones inteligentes aplicadas al contexto real",
                    "weight_percent": 35.0,
                    "levels": _std_levels(
                        "Propuesta pertinente, bien fundamentada y alineada con retos reales de Manizales Resiliente.",
                        "Propuesta clara y funcional con buena articulación conceptual.",
                        "Propuesta básica con justificación parcial del impacto o enfoque IA.",
                        "Propuesta incompleta o desconectada de los objetivos del laboratorio.",
                    ),
                },
                {
                    "id": "c2",
                    "name": "Implementación técnica y verificación del código",
                    "competency": "Desarrollo y verificación de software asistido por IA",
                    "weight_percent": 40.0,
                    "levels": _std_levels(
                        "Código funcional, limpio, modular, sin errores de sintaxis y con pruebas verificables.",
                        "Implementación funcional con calidad técnica adecuada y observaciones menores.",
                        "Código parcialmente funcional o con advertencias importantes de calidad.",
                        "Errores graves de ejecución/sintaxis o ausencia de implementación verificable.",
                    ),
                },
                {
                    "id": "c3",
                    "name": "Calidad del informe, evidencias y reflexión sobre uso de IA",
                    "competency": "Comunicación técnica y criterio ingenieril",
                    "weight_percent": 25.0,
                    "levels": _std_levels(
                        "Informe riguroso con evidencias concretas, análisis de resultados y uso crítico de IA.",
                        "Informe bien estructurado con evidencias claras del proceso.",
                        "Informe descriptivo con análisis superficial de resultados.",
                        "Informe incompleto o sin evidencias verificables.",
                    ),
                },
            ],
        ),
        (
            c1_id,
            "LAB-1.3",
            "Laboratorio 3: CVDS Aumentado",
            "Aplicación de la Inteligencia Artificial de forma sistemática a lo largo del Ciclo de Vida de Desarrollo de Software (CVDS): ingeniería de requisitos, diseño de arquitectura, codificación, pruebas, documentación y validación humana.",
            [
                "Incorporar asistentes y agentes de IA en las fases clave del Ciclo de Vida de Desarrollo de Software.",
                "Validar y mejorar críticamente los artefactos generados con asistencia de IA.",
                "Evidenciar trazabilidad de decisiones técnicas, pruebas y calidad del producto entregado.",
            ],
            ["CVDS Aumentado por IA", "Ingeniería de Requisitos y Arquitectura con IA", "Pruebas y Validación Asistida"],
            [
                {
                    "id": "c1",
                    "name": "Integración de IA en las fases del CVDS",
                    "competency": "Gestión del ciclo de vida de software aumentado por IA",
                    "weight_percent": 40.0,
                    "levels": _std_levels(
                        "Evidencia uso estructurado y crítico de IA en requisitos, diseño, implementación y pruebas.",
                        "Aplica IA en la mayoría de fases del CVDS con buen criterio técnico.",
                        "Uso limitado de IA concentrado solo en generación aislada de código.",
                        "No evidencia integración metodológica de IA en el CVDS.",
                    ),
                },
                {
                    "id": "c2",
                    "name": "Calidad técnica del software y pruebas",
                    "competency": "Ingeniería de software y aseguramiento de calidad",
                    "weight_percent": 35.0,
                    "levels": _std_levels(
                        "Arquitectura limpia, código sin errores estáticos y pruebas automatizadas aprobadas.",
                        "Software funcional y organizado con pruebas básicas.",
                        "Código funcional con deuda técnica o pruebas insuficientes.",
                        "Errores de sintaxis o fallos críticos en la solución.",
                    ),
                },
                {
                    "id": "c3",
                    "name": "Documentación, trazabilidad y reflexión crítica",
                    "competency": "Criterio técnico y documentación de ingeniería",
                    "weight_percent": 25.0,
                    "levels": _std_levels(
                        "Documenta herramientas IA, aportes, limitaciones y decisiones humanas con gran claridad.",
                        "Documentación completa y coherente con el desarrollo realizado.",
                        "Documentación breve sin reflexión sobre limitaciones de la IA.",
                        "Documentación ausente o inconsistente.",
                    ),
                },
            ],
        ),
        (
            c2_id,
            "LAB-2.1",
            "Laboratorio 1: Organizador de Archivos Python",
            "Desarrollo de una herramienta en Python para la clasificación y organización automatizada de archivos aplicando buenas prácticas de programación, manejo seguro del sistema de archivos, pruebas unitarias y asistencia/integración con IA.",
            [
                "Implementar un organizador automático de archivos en Python modular y seguro.",
                "Manejar correctamente rutas, extensiones, excepciones y casos borde sin pérdida de datos.",
                "Validar el funcionamiento mediante pruebas unitarias automatizadas y documentar el diseño.",
            ],
            ["Automatización en Python", "Ingeniería de Software y Testing", "Asistencia e Integración de IA"],
            [
                {
                    "id": "c1",
                    "name": "Funcionalidad y lógica de organización de archivos",
                    "competency": "Desarrollo de utilidades automatizadas en Python",
                    "weight_percent": 40.0,
                    "levels": _std_levels(
                        "Clasifica y organiza archivos con precisión, manejo de duplicados, excepciones y casos borde.",
                        "Organizador funcional con buen manejo de reglas y rutas.",
                        "Cumple organización básica con fallos en nombres repetidos o errores de ruta.",
                        "No organiza archivos correctamente o falla al ejecutarse.",
                    ),
                },
                {
                    "id": "c2",
                    "name": "Calidad de código Python, análisis estático y pruebas unitarias",
                    "competency": "Calidad de código y verificación automatizada",
                    "weight_percent": 35.0,
                    "levels": _std_levels(
                        "Código Python limpio (sin errores AST ni Ruff) y suite pytest completa aprobada en sandbox.",
                        "Código bien estructurado con pruebas unitarias funcionales.",
                        "Advertencias estáticas relevantes o cobertura mínima de pruebas.",
                        "Errores de sintaxis, sin pruebas o pruebas fallidas.",
                    ),
                },
                {
                    "id": "c3",
                    "name": "Informe técnico, evidencias y recomendaciones de mejora",
                    "competency": "Documentación y análisis técnico",
                    "weight_percent": 25.0,
                    "levels": _std_levels(
                        "Informe claro con arquitectura, evidencias de ejecución, uso de IA y conclusiones sólidas.",
                        "Informe ordenado que explica correctamente la solución y sus pruebas.",
                        "Informe superficial con pocas evidencias técnicas.",
                        "Informe incompleto o ilegible.",
                    ),
                },
            ],
        ),
    ]


def ensure_course_labs(db: Session, teacher_id: int | None = None) -> list[Lab]:
    """Insert the default real course labs (Cohorte 1 & Cohorte 2) if they do not exist yet."""
    c1 = db.query(Cohort).filter(Cohort.number == 1).first()
    c2 = db.query(Cohort).filter(Cohort.number == 2).first()
    if not c1 or not c2:
        return []

    created: list[Lab] = []
    for cohort_id, code, title, desc, objs, topics, criteria in get_default_labs_spec(c1.id, c2.id):
        existing = db.query(Lab).filter(Lab.code == code).first()
        if existing:
            continue
        lab = Lab(
            cohort_id=cohort_id,
            code=code,
            title=title,
            description=desc,
            objectives=objs,
            ai_topics=topics,
            created_by=teacher_id,
        )
        db.add(lab)
        db.flush()
        rv = RubricVersion(
            lab_id=lab.id,
            version_number=1,
            title=f"Rúbrica {code} — {title} (v1)",
            is_active=True,
            criteria_json=criteria,
            total_weight=100.0,
            created_by=teacher_id,
        )
        db.add(rv)
        db.flush()
        created.append(lab)

    db.commit()
    return created


def seed_initial_data(db: Session) -> None:
    """Populate initial accounts, Cohorte 1 & Cohorte 2, and real course labs if DB is empty."""
    if not db.query(AISettingsModel).filter(AISettingsModel.id == 1).first():
        db.add(
            AISettingsModel(
                id=1,
                provider=settings.AI_PROVIDER,
                model_name=settings.GEMINI_MODEL,
                base_url="",
                api_key_override="",
            )
        )
        db.commit()

    if db.query(User).count() > 0:
        return

    teacher = User(
        full_name="Prof. Carlos Andrés Mejía",
        email="docente@umanizales.edu.co",
        hashed_password=hash_password("Docente123!"),
        role="teacher",
    )
    student = User(
        full_name="Julian Sanchez",
        email="estudiante@umanizales.edu.co",
        hashed_password=hash_password("Estudiante123!"),
        role="student",
    )
    db.add_all([teacher, student])
    db.flush()

    c1 = Cohort(
        number=1,
        name="Cohorte 1",
        description="Laboratorios prácticos correspondientes a la Cohorte 1 del curso de Inteligencia Artificial.",
    )
    c2 = Cohort(
        number=2,
        name="Cohorte 2",
        description="Laboratorios prácticos correspondientes a la Cohorte 2 del curso de Inteligencia Artificial.",
    )
    db.add_all([c1, c2])
    db.flush()

    ensure_course_labs(db, teacher_id=teacher.id)
