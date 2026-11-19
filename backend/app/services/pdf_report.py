import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def generate_integrated_report_pdf(report: dict) -> bytes:
    """Generate a clean, downloadable PDF for the Integrated Learning Report."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleCustom",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "SubCustom",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#475569"),
        spaceAfter=14,
    )
    h2_style = ParagraphStyle(
        "H2Custom",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#1d4ed8"),
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle("BodyCustom", parent=styles["Normal"], fontSize=9.5, leading=13)

    story = []
    student = report["student"]
    ov = report["overview"]

    story.append(Paragraph("Informe Integral de Aprendizaje en Inteligencia Artificial", title_style))
    story.append(
        Paragraph(
            f"Estudiante: <b>{student['full_name']}</b> ({student['email']}) &nbsp;|&nbsp; "
            f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            subtitle_style,
        )
    )

    # KPI Summary Table
    kpi_data = [
        ["Promedio Global", "Nivel de Dominio", "Labs Evaluados", "Cohorte 1", "Cohorte 2"],
        [
            f"{ov['overall_average']} / 5.0",
            str(ov["overall_mastery_level"]).upper(),
            f"{ov['labs_evaluated']} / {ov['total_labs_course']}",
            f"{ov['cohort_1_average']}/5.0" if ov["cohort_1_average"] is not None else "N/A",
            f"{ov['cohort_2_average']}/5.0" if ov["cohort_2_average"] is not None else "N/A",
        ],
    ]
    kpi_table = Table(kpi_data, colWidths=[3.4 * cm, 3.6 * cm, 3.2 * cm, 3.4 * cm, 3.4 * cm])
    kpi_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#f1f5f9")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(kpi_table)
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"<b>Evolución del aprendizaje:</b> {ov['evolution_trend']}", body_style))

    # Lab Results Table
    story.append(Paragraph("1. Resultados Consolidados por Laboratorio", h2_style))
    lab_rows = [["Cohorte", "Laboratorio", "Nota Final", "Estado", "Pruebas Sandbox"]]
    for item in report["lab_results"]:
        lab_rows.append([
            f"C{item['cohort_number']}",
            Paragraph(f"<b>{item['lab_code']}</b> - {item['lab_title']}", body_style),
            f"{item['final_grade']} / 5.0",
            "Aprobada" if item["status"] == "approved" else "Preliminar",
            f"{item['sandbox_passed']} OK / {item['sandbox_failed']} Fail",
        ])
    if len(lab_rows) == 1:
        lab_rows.append(["-", "Sin laboratorios evaluados todavía", "-", "-", "-"])

    lab_table = Table(lab_rows, colWidths=[1.8 * cm, 7.6 * cm, 2.4 * cm, 2.4 * cm, 2.8 * cm])
    lab_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ])
    )
    story.append(lab_table)

    # Competencies Table
    story.append(Paragraph("2. Competencias y Niveles de Dominio", h2_style))
    comp_rows = [["Temática", "Categoría", "Dominio", "Puntaje"]]
    for comp in report["competencies"]:
        comp_rows.append([
            Paragraph(comp["topic"], body_style),
            Paragraph(comp["category"], body_style),
            comp["mastery_level"].upper(),
            f"{comp['mastery_score']} / 5.0",
        ])
    if len(comp_rows) == 1:
        comp_rows.append(["Sin datos", "-", "-", "-"])

    comp_table = Table(comp_rows, colWidths=[5.5 * cm, 5.5 * cm, 3.2 * cm, 2.8 * cm])
    comp_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0fdfa")]),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ])
    )
    story.append(comp_table)

    # Strengthening Plan
    story.append(Paragraph("3. Plan Personalizado de Fortalecimiento", h2_style))
    for step in report["strengthening_plan"]:
        story.append(
            Paragraph(
                f"<b>Paso {step['step']} [{step['priority']}] — {step['topic']}:</b> "
                f"{step['action']}<br/><i>Práctica sugerida:</i> {step['suggested_practice']}",
                body_style,
            )
        )
        story.append(Spacer(1, 5))

    doc.build(story)
    return buffer.getvalue()
