import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  CheckCircle2,
  Cpu,
  History,
  Lock,
  ShieldCheck,
  Terminal,
  AlertTriangle,
  Sparkles,
  BookOpen,
} from 'lucide-react';
import { apiFetch } from '../api/client';
import { useAuth } from '../context/AuthContext';
import StatusBadge from '../components/StatusBadge';

export default function EvaluationDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [ev, setEv] = useState(null);
  const [loading, setLoading] = useState(true);
  const [teacherComments, setTeacherComments] = useState('');
  const [ratios, setRatios] = useState({});
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');

  const loadEval = () => {
    apiFetch(`/api/evaluations/${id}`)
      .then((data) => {
        setEv(data);
        setTeacherComments(data.teacher_comments || '');
        const map = {};
        data.criteria_evaluations.forEach((c) => {
          map[c.criterion_id] = c.score_ratio;
        });
        setRatios(map);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadEval();
  }, [id]);

  const handleTeacherSave = async (approve) => {
    setSaving(true);
    setMsg('');
    try {
      const updated = await apiFetch(`/api/evaluations/${id}/review`, {
        method: 'PUT',
        body: JSON.stringify({
          adjusted_criteria_ratios: ratios,
          teacher_comments: teacherComments,
          approve,
        }),
      });
      setEv(updated);
      setMsg(approve ? 'Evaluación aprobada y publicada oficialmente.' : 'Ajustes guardados en el historial de auditoría.');
    } catch (err) {
      setMsg(`Error: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="p-8 text-sm text-slate-500">Cargando evaluación detallada...</div>;
  if (!ev) return <div className="p-8 text-sm text-rose-600">No se encontró la evaluación solicitada.</div>;

  const sb = ev.sandbox_result || {};

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link to="/portfolio" className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:underline mb-1">
            <ArrowLeft className="w-3.5 h-3.5" /> Volver al Portafolio
          </Link>
          <h1 className="text-2xl font-bold text-slate-900">
            {ev.lab_code}: {ev.lab_title}
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Estudiante: <strong>{ev.student_name}</strong> · Cohorte {ev.cohort_number} · Rúbrica: <strong>{ev.rubric_title} (v{ev.rubric_version_number})</strong>
          </p>
        </div>
        <div className="flex items-center gap-4 bg-white border border-slate-200 rounded-xl px-5 py-3 shadow-xs">
          <div>
            <p className="text-[11px] uppercase font-bold text-slate-400">Nota Final (Backend)</p>
            <p className="text-3xl font-extrabold text-indigo-700">{ev.final_grade} <span className="text-sm font-normal text-slate-400">/ 5.0</span></p>
            <p className="text-[11px] text-slate-500">Preliminar IA: {ev.preliminary_grade}/5.0</p>
          </div>
          <StatusBadge value={ev.status} />
        </div>
      </div>

      {/* Pedagogical Synthesis */}
      <div className="grid md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <h2 className="text-xs font-bold uppercase text-indigo-700 mb-2 flex items-center gap-1.5">
            <Sparkles className="w-4 h-4" /> Resumen Evaluativo
          </h2>
          <p className="text-sm text-slate-700 leading-relaxed">{ev.summary}</p>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <h2 className="text-xs font-bold uppercase text-emerald-700 mb-2 flex items-center gap-1.5">
            <BookOpen className="w-4 h-4" /> ¿Qué aprendió el estudiante?
          </h2>
          <p className="text-sm text-slate-700 leading-relaxed">{ev.what_student_learned}</p>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <h2 className="text-xs font-bold uppercase text-sky-700 mb-2 flex items-center gap-1.5">
            <Cpu className="w-4 h-4" /> ¿Cómo aplicó sus conocimientos?
          </h2>
          <p className="text-sm text-slate-700 leading-relaxed">{ev.how_applied_knowledge}</p>
        </div>
      </div>

      {/* Criterion-by-Criterion Rubric Evaluation */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
          <div>
            <h2 className="font-bold text-slate-900 text-sm">Valoración Detallada por Criterio de Rúbrica</h2>
            <p className="text-xs text-slate-500">
              Cálculo determinista en backend: Σ (Peso % × Nota del criterio) = <strong>{ev.final_grade} / 5.0</strong>
            </p>
          </div>
        </div>
        <div className="divide-y divide-slate-100">
          {ev.criteria_evaluations.map((c) => (
            <div key={c.criterion_id} className="p-5 space-y-2.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <span className="text-xs font-bold text-indigo-700 mr-2">[{c.weight_percent}%]</span>
                  <span className="font-bold text-sm text-slate-900">{c.criterion_name}</span>
                  <p className="text-xs text-slate-500">Competencia: {c.competency}</p>
                </div>
                <div className="flex items-center gap-2.5">
                  <StatusBadge value={c.level_achieved} />
                  <span className="text-sm font-bold text-slate-900">
                    {c.criterion_grade_5}/5.0 <span className="text-xs font-normal text-slate-400">(+{c.weighted_contribution})</span>
                  </span>
                </div>
              </div>
              <p className="text-xs text-slate-700 leading-relaxed">{c.justification}</p>
              <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                <p className="text-[11px] font-bold uppercase text-slate-500 mb-1">Evidencias concretas citadas:</p>
                <ul className="list-disc pl-4 text-xs text-slate-700 space-y-0.5">
                  {c.evidences.map((evi, i) => <li key={i}>{evi}</li>)}
                </ul>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Strengths, Weaknesses, Recommendations */}
      <div className="grid md:grid-cols-3 gap-4">
        <div className="bg-emerald-50/60 border border-emerald-200 rounded-xl p-5">
          <h3 className="text-xs font-bold uppercase text-emerald-800 mb-2">Fortalezas</h3>
          <ul className="list-disc pl-4 text-xs text-emerald-950 space-y-1.5">
            {ev.strengths.map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        </div>
        <div className="bg-amber-50/60 border border-amber-200 rounded-xl p-5">
          <h3 className="text-xs font-bold uppercase text-amber-800 mb-2">Debilidades / Brechas</h3>
          <ul className="list-disc pl-4 text-xs text-amber-950 space-y-1.5">
            {ev.weaknesses.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
        <div className="bg-indigo-50/60 border border-indigo-200 rounded-xl p-5">
          <h3 className="text-xs font-bold uppercase text-indigo-800 mb-2">Recomendaciones Personalizadas</h3>
          <ul className="list-disc pl-4 text-xs text-indigo-950 space-y-1.5">
            {ev.recommendations.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        </div>
      </div>

      {/* Objective Sandbox Verification & Traceability */}
      <div className="grid lg:grid-cols-2 gap-6">
        <div className="bg-slate-900 text-slate-100 rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold flex items-center gap-2">
              <Terminal className="w-4 h-4 text-emerald-400" />
              Verificación Objetiva en Sandbox Aislado
            </h3>
            <span className="inline-flex items-center gap-1 text-[11px] px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-semibold">
              <Lock className="w-3 h-3" /> Red bloqueada · {sb.sandbox_mode}
            </span>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="bg-slate-800 rounded-lg p-2.5">
              <p className="text-[10px] text-slate-400 uppercase">Sintaxis AST</p>
              <p className={`text-sm font-bold mt-0.5 ${sb.syntax_ok ? 'text-emerald-400' : 'text-rose-400'}`}>
                {sb.syntax_ok ? 'Válida' : 'Errores'}
              </p>
            </div>
            <div className="bg-slate-800 rounded-lg p-2.5">
              <p className="text-[10px] text-slate-400 uppercase">Ruff Estático</p>
              <p className="text-sm font-bold text-amber-300 mt-0.5">{sb.static_issues_count ?? 0} alertas</p>
            </div>
            <div className="bg-slate-800 rounded-lg p-2.5">
              <p className="text-[10px] text-slate-400 uppercase">Pytest</p>
              <p className="text-sm font-bold text-sky-300 mt-0.5">
                {sb.unit_tests_passed ?? 0} OK / {sb.unit_tests_failed ?? 0} Fail
              </p>
            </div>
          </div>
          <p className="text-[11px] text-slate-400">
            Límites: {sb.timeout_seconds}s timeout · {sb.memory_limit_mb} MB RAM · Tiempo: {sb.execution_time_ms} ms · {sb.total_lines_of_code} líneas analizadas.
          </p>
          <pre className="bg-slate-950 rounded-lg p-3 text-[11px] text-slate-300 overflow-x-auto max-h-40">
            {sb.unit_tests_output || 'Sin salida de pruebas.'}
          </pre>
          {sb.static_issues?.length > 0 && (
            <div className="text-[11px] text-amber-300 space-y-0.5">
              <p className="font-bold">Hallazgos análisis estático:</p>
              {sb.static_issues.slice(0, 6).map((iss, i) => <div key={i}>• {iss}</div>)}
            </div>
          )}
        </div>

        {/* Traceability & Audit Trail */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-3 shadow-xs">
          <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <History className="w-4 h-4 text-indigo-600" />
            Trazabilidad y Auditoría
          </h3>
          <div className="grid grid-cols-2 gap-2 text-xs bg-slate-50 p-3 rounded-lg border border-slate-200">
            <div><span className="text-slate-500">Modelo IA:</span> <strong>{ev.ai_provider} / {ev.ai_model_used}</strong></div>
            <div><span className="text-slate-500">Rúbrica:</span> <strong>v{ev.rubric_version_number} (ID #{ev.rubric_version_id})</strong></div>
            <div><span className="text-slate-500">Archivos código:</span> <strong>{(ev.evidence_snapshot?.files_analyzed || []).length}</strong></div>
            <div><span className="text-slate-500">Imágenes PDF:</span> <strong>{ev.evidence_snapshot?.pdf_images_analyzed ?? 0}</strong></div>
          </div>
          {ev.evidence_snapshot?.fallback_note && (
            <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-800 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{ev.evidence_snapshot.fallback_note}</span>
            </div>
          )}
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {ev.audit_logs.map((log) => (
              <div key={log.id} className="text-xs p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                <div className="flex justify-between">
                  <span className="font-bold text-slate-800">{log.action} · {log.actor_name}</span>
                  <span className="text-slate-400">{new Date(log.created_at).toLocaleString()}</span>
                </div>
                <p className="text-slate-600 mt-0.5">{log.notes}</p>
                {log.new_grade != null && (
                  <p className="text-[11px] text-indigo-700 font-semibold mt-0.5">
                    Nota: {log.previous_grade != null ? `${log.previous_grade} → ` : ''}{log.new_grade}/5.0
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Teacher Comments Display (visible to student too) */}
      {ev.teacher_comments && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-sm text-emerald-900">
          <p className="font-bold text-xs uppercase text-emerald-700 mb-1">
            Observaciones del Docente ({ev.reviewed_by_name || 'Docente'})
          </p>
          <p>{ev.teacher_comments}</p>
        </div>
      )}

      {/* Teacher Review & Approval Panel */}
      {user?.role === 'teacher' && (
        <div className="bg-white rounded-xl border-2 border-indigo-200 p-6 shadow-xs space-y-4">
          <h2 className="font-bold text-slate-900 text-base flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-indigo-600" />
            Panel de Supervisión, Ajuste y Aprobación Docente
          </h2>
          <p className="text-xs text-slate-500">
            Ajusta el porcentaje de logro por criterio (el backend recalcula automáticamente la nota ponderada 0.0–5.0) y aprueba para publicación oficial.
          </p>

          {msg && (
            <div className="p-3 rounded-lg bg-indigo-50 border border-indigo-200 text-xs font-semibold text-indigo-800">
              {msg}
            </div>
          )}

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {ev.criteria_evaluations.map((c) => (
              <div key={c.criterion_id} className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                <p className="text-xs font-bold text-slate-800">{c.criterion_name} ({c.weight_percent}%)</p>
                <div className="flex items-center gap-2 mt-2">
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.02"
                    value={ratios[c.criterion_id] ?? c.score_ratio}
                    onChange={(e) => setRatios({ ...ratios, [c.criterion_id]: Number(e.target.value) })}
                    className="flex-1"
                  />
                  <span className="text-xs font-bold text-indigo-700 w-16 text-right">
                    {((ratios[c.criterion_id] ?? c.score_ratio) * 5).toFixed(2)}/5
                  </span>
                </div>
              </div>
            ))}
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Comentarios de validación docente</label>
            <textarea
              rows={2}
              value={teacherComments}
              onChange={(e) => setTeacherComments(e.target.value)}
              placeholder="Justificación de ajustes o retroalimentación final del docente..."
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
            />
          </div>

          <div className="flex flex-wrap justify-end gap-2">
            <button
              type="button"
              disabled={saving}
              onClick={() => handleTeacherSave(false)}
              className="px-4 py-2 rounded-lg border border-slate-300 hover:bg-slate-100 text-xs font-semibold cursor-pointer"
            >
              Guardar Ajuste (Sin aprobar aún)
            </button>
            <button
              type="button"
              disabled={saving}
              onClick={() => handleTeacherSave(true)}
              className="inline-flex items-center gap-1.5 px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold cursor-pointer"
            >
              <CheckCircle2 className="w-4 h-4" /> Aprobar y Publicar Evaluación
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
