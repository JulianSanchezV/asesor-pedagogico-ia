from collections import defaultdict
from sqlalchemy.orm import Session
from app.models import Cohort, Evaluation, Lab, Submission, User


def _mastery_from_score(score: float) -> str:
    if score >= 4.3:
        return "avanzado"
    if score >= 3.5:
        return "intermedio"
    if score >= 2.8:
        return "basico"
    return "por_fortalecer"


def _get_student_latest_evaluations(db: Session, student_id: int) -> list[tuple[Submission, Evaluation, Lab, Cohort]]:
    submissions = (
        db.query(Submission)
        .filter(Submission.student_id == student_id)
        .order_by(Submission.created_at.asc())
        .all()
    )
    latest_by_lab: dict[int, tuple[Submission, Evaluation, Lab, Cohort]] = {}
    for sub in submissions:
        if not sub.evaluations:
            continue
        # Prefer latest approved evaluation; otherwise latest preliminary evaluation
        approved = [e for e in sub.evaluations if e.status == "approved"]
        chosen_eval = approved[0] if approved else sub.evaluations[0]
        lab = sub.lab
        cohort = lab.cohort
        latest_by_lab[lab.id] = (sub, chosen_eval, lab, cohort)

    records = list(latest_by_lab.values())
    records.sort(key=lambda item: (item[3].number, item[2].code))
    return records


def build_integrated_report(db: Session, student_id: int) -> dict:
    """
    Mandatory Feature #5:
    Consolidate results across all labs in Cohorts 1 & 2 for a student:
    grades, acquired competencies, mastery levels, evolution, gaps & personalized strengthening plan.
    """
    student = db.query(User).filter(User.id == student_id).first()
    if not student:
        raise ValueError("Estudiante no encontrado.")

    records = _get_student_latest_evaluations(db, student_id)
    total_labs_course = db.query(Lab).count()

    lab_results = []
    cohort_grades: dict[int, list[float]] = defaultdict(list)
    competency_agg: dict[str, dict] = {}
    all_weaknesses: list[str] = []
    all_recommendations: list[str] = []

    for sub, ev, lab, cohort in records:
        grade = round(float(ev.final_grade), 2)
        cohort_grades[cohort.number].append(grade)
        lab_results.append({
            "lab_id": lab.id,
            "lab_code": lab.code,
            "lab_title": lab.title,
            "cohort_number": cohort.number,
            "cohort_name": cohort.name,
            "evaluation_id": ev.id,
            "submission_id": sub.id,
            "preliminary_grade": ev.preliminary_grade,
            "final_grade": grade,
            "status": ev.status,
            "ai_model_used": f"{ev.ai_provider}/{ev.ai_model_used}",
            "what_student_learned": ev.what_student_learned,
            "sandbox_passed": (ev.sandbox_result_json or {}).get("unit_tests_passed", 0),
            "sandbox_failed": (ev.sandbox_result_json or {}).get("unit_tests_failed", 0),
            "evaluated_at": ev.created_at.isoformat() if ev.created_at else None,
        })

        for w in ev.weaknesses_json or []:
            if w not in all_weaknesses:
                all_weaknesses.append(w)
        for r in ev.recommendations_json or []:
            if r not in all_recommendations:
                all_recommendations.append(r)

        for comp in ev.competencies_snapshot_json or []:
            topic = comp.get("topic", "IA General").strip()
            key = topic.lower()
            if key not in competency_agg:
                competency_agg[key] = {
                    "topic": topic,
                    "category": comp.get("category", "Inteligencia Artificial"),
                    "scores": [],
                    "labs": [],
                    "evidences": [],
                    "needs_deepening": [],
                }
            competency_agg[key]["scores"].append(float(comp.get("mastery_score", grade)))
            if lab.code not in competency_agg[key]["labs"]:
                competency_agg[key]["labs"].append(f"{lab.code}: {lab.title}")
            if comp.get("evidence"):
                competency_agg[key]["evidences"].append(f"[{lab.code}] {comp['evidence']}")
            for nd in comp.get("needs_deepening", []):
                if nd not in competency_agg[key]["needs_deepening"]:
                    competency_agg[key]["needs_deepening"].append(nd)

    all_grades = [r["final_grade"] for r in lab_results]
    overall_avg = round(sum(all_grades) / len(all_grades), 2) if all_grades else 0.0
    c1_avg = round(sum(cohort_grades[1]) / len(cohort_grades[1]), 2) if cohort_grades[1] else None
    c2_avg = round(sum(cohort_grades[2]) / len(cohort_grades[2]), 2) if cohort_grades[2] else None

    if c1_avg is not None and c2_avg is not None:
        delta = round(c2_avg - c1_avg, 2)
        if delta > 0.15:
            evolution_trend = f"Progreso positivo (+{delta} puntos entre Cohorte 1 y Cohorte 2)."
        elif delta < -0.15:
            evolution_trend = f"Descenso de {delta} puntos en Cohorte 2; se recomienda reforzar temáticas avanzadas."
        else:
            evolution_trend = f"Desempeño estable entre ambas cohortes (variación de {delta} puntos)."
    elif all_grades:
        evolution_trend = "Evaluación parcial en curso; completa entregas en ambas cohortes para comparar evolución."
    else:
        evolution_trend = "Aún no existen laboratorios evaluados para este estudiante."

    competencies_summary = []
    gaps = []
    for item in competency_agg.values():
        avg_s = round(sum(item["scores"]) / len(item["scores"]), 2)
        level = _mastery_from_score(avg_s)
        entry = {
            "topic": item["topic"],
            "category": item["category"],
            "mastery_score": avg_s,
            "mastery_level": level,
            "labs_applied": item["labs"],
            "evidences": item["evidences"],
            "needs_deepening": item["needs_deepening"],
        }
        competencies_summary.append(entry)
        if avg_s < 4.0 or item["needs_deepening"]:
            gaps.append({
                "topic": item["topic"],
                "category": item["category"],
                "current_score": avg_s,
                "mastery_level": level,
                "gap_detail": item["needs_deepening"][0] if item["needs_deepening"] else "Requiere consolidación práctica.",
            })

    competencies_summary.sort(key=lambda x: x["mastery_score"], reverse=True)
    gaps.sort(key=lambda x: x["current_score"])

    # Personalized strengthening plan
    strengthening_plan = []
    for idx, gap in enumerate(gaps[:5], start=1):
        priority = "Alta" if gap["current_score"] < 3.5 else "Media"
        strengthening_plan.append({
            "step": idx,
            "priority": priority,
            "topic": gap["topic"],
            "action": gap["gap_detail"],
            "suggested_practice": f"Revisar evidencias previas en {gap['topic']}, añadir pruebas unitarias de casos borde y documentar métricas comparativas.",
        })
    if not strengthening_plan and all_grades:
        strengthening_plan.append({
            "step": 1,
            "priority": "Baja",
            "topic": "Profundización Avanzada en IA",
            "action": "Mantener el nivel de excelencia explorando despliegue en producción, optimización de inferencia y evaluación ética.",
            "suggested_practice": "Integrar benchmarks reproducibles y documentación técnica avanzada.",
        })

    return {
        "student": {
            "id": student.id,
            "full_name": student.full_name,
            "email": student.email,
        },
        "overview": {
            "overall_average": overall_avg,
            "overall_mastery_level": _mastery_from_score(overall_avg) if all_grades else "sin_datos",
            "labs_evaluated": len(lab_results),
            "total_labs_course": total_labs_course,
            "cohort_1_average": c1_avg,
            "cohort_2_average": c2_avg,
            "evolution_trend": evolution_trend,
        },
        "lab_results": lab_results,
        "competencies": competencies_summary,
        "gaps": gaps,
        "strengths_and_weaknesses": {
            "recurring_weaknesses": all_weaknesses[:8],
            "key_recommendations": all_recommendations[:8],
        },
        "strengthening_plan": strengthening_plan,
    }


def build_interactive_mind_map(db: Session, student_id: int) -> dict:
    """
    Mandatory Feature #6:
    Auto-generate interactive mind map integrating AI themes, categories and relationships
    across Cohort 1 & 2 labs, including per-topic labs applied, evidences, mastery level,
    and aspects requiring deepening.
    """
    report = build_integrated_report(db, student_id)
    student_name = report["student"]["full_name"]
    overall_avg = report["overview"]["overall_average"]

    nodes = []
    edges = []

    root_id = "root-ia"
    nodes.append({
        "id": root_id,
        "type": "root",
        "label": f"Competencias en IA\n({student_name})",
        "category": "Curso IA - Cohortes 1 y 2",
        "mastery_score": overall_avg,
        "mastery_level": report["overview"]["overall_mastery_level"],
        "labs_applied": [f"{r['lab_code']}: {r['lab_title']}" for r in report["lab_results"]],
        "evidences": [f"Promedio global: {overall_avg}/5.0 en {report['overview']['labs_evaluated']} laboratorios."],
        "needs_deepening": [g["gap_detail"] for g in report["gaps"][:3]],
        "position": {"x": 450, "y": 40},
    })

    # Group topics by category
    by_category: dict[str, list[dict]] = defaultdict(list)
    for comp in report["competencies"]:
        by_category[comp["category"]].append(comp)

    # Also include course topics not yet evaluated so the map shows full curriculum coverage
    all_labs = db.query(Lab).order_by(Lab.cohort_id, Lab.code).all()
    evaluated_topics_lower = {c["topic"].lower() for c in report["competencies"]}
    for lab in all_labs:
        for topic in lab.ai_topics or []:
            if topic.lower() not in evaluated_topics_lower:
                evaluated_topics_lower.add(topic.lower())
                cat = f"Cohorte {lab.cohort.number}"
                by_category[cat].append({
                    "topic": topic,
                    "category": cat,
                    "mastery_score": 0.0,
                    "mastery_level": "pendiente",
                    "labs_applied": [f"{lab.code}: {lab.title} (pendiente de entrega/evaluación)"],
                    "evidences": ["Sin entrega evaluada todavía."],
                    "needs_deepening": [f"Completar y entregar el laboratorio {lab.code}."],
                })

    categories = list(by_category.items())
    cat_spacing_x = 340
    start_x = 450 - int(((len(categories) - 1) * cat_spacing_x) / 2)

    topic_nodes_by_lab: dict[str, list[str]] = defaultdict(list)

    for c_idx, (cat_name, topics) in enumerate(categories):
        cat_id = f"cat-{c_idx}"
        cat_x = start_x + c_idx * cat_spacing_x
        cat_y = 210
        scored = [t["mastery_score"] for t in topics if t["mastery_score"] > 0]
        cat_avg = round(sum(scored) / len(scored), 2) if scored else 0.0

        nodes.append({
            "id": cat_id,
            "type": "category",
            "label": cat_name,
            "category": cat_name,
            "mastery_score": cat_avg,
            "mastery_level": _mastery_from_score(cat_avg) if scored else "pendiente",
            "labs_applied": sorted({lb for t in topics for lb in t["labs_applied"]}),
            "evidences": [f"{len(topics)} temáticas agrupadas en esta categoría."],
            "needs_deepening": [nd for t in topics for nd in t["needs_deepening"]][:4],
            "position": {"x": cat_x, "y": cat_y},
        })
        edges.append({
            "id": f"e-{root_id}-{cat_id}",
            "source": root_id,
            "target": cat_id,
            "label": "incluye",
            "relation_type": "hierarchy",
        })

        topic_spacing_x = 220
        t_start_x = cat_x - int(((len(topics) - 1) * topic_spacing_x) / 2)
        for t_idx, topic in enumerate(topics):
            t_id = f"topic-{c_idx}-{t_idx}"
            t_x = t_start_x + t_idx * topic_spacing_x
            t_y = 400 + (t_idx % 2) * 85

            nodes.append({
                "id": t_id,
                "type": "topic",
                "label": topic["topic"],
                "category": cat_name,
                "mastery_score": topic["mastery_score"],
                "mastery_level": topic["mastery_level"],
                "labs_applied": topic["labs_applied"],
                "evidences": topic["evidences"],
                "needs_deepening": topic["needs_deepening"],
                "position": {"x": t_x, "y": t_y},
            })
            edges.append({
                "id": f"e-{cat_id}-{t_id}",
                "source": cat_id,
                "target": t_id,
                "label": topic["mastery_level"],
                "relation_type": "hierarchy",
            })
            for lb in topic["labs_applied"]:
                lab_key = lb.split(":")[0].strip()
                topic_nodes_by_lab[lab_key].append(t_id)

    # Conceptual cross-links between topics applied in the same laboratory
    seen_pairs = set()
    for lab_key, node_ids in topic_nodes_by_lab.items():
        for i in range(len(node_ids) - 1):
            a, b = node_ids[i], node_ids[i + 1]
            pair = tuple(sorted((a, b)))
            if a != b and pair not in seen_pairs:
                seen_pairs.add(pair)
                edges.append({
                    "id": f"rel-{a}-{b}",
                    "source": a,
                    "target": b,
                    "label": f"co-aplicado en {lab_key}",
                    "relation_type": "conceptual",
                })

    return {
        "student": report["student"],
        "summary": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "overall_average": overall_avg,
        },
        "nodes": nodes,
        "edges": edges,
    }
