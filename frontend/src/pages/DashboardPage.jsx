import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Award,
  BookOpenCheck,
  CheckCircle2,
  Clock,
  Cpu,
  FolderKanban,
  Network,
  ArrowRight,
  FileBarChart2,
} from 'lucide-react';
import { apiFetch } from '../api/client';
import { useAuth } from '../context/AuthContext';
import StatusBadge from '../components/StatusBadge';

export default function DashboardPage() {
  const { user } = useAuth();
  const [labs, setLabs] = useState([]);
  const [submissions, setSubmissions] = useState([]);
  const [report, setReport] = useState(null);
  const [aiCfg, setAiCfg] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiFetch('/api/labs'),
      apiFetch('/api/submissions'),
      apiFetch('/api/reports/integrated').catch(() => null),
      apiFetch('/api/settings/ai').catch(() => null),
    ])
      .then(([labsData, subsData, repData, aiData]) => {
        setLabs(labsData);
        setSubmissions(subsData);
        setReport(repData);
        setAiCfg(aiData);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="p-8 text-sm text-slate-500">Cargando panel principal...</div>;
  }

  const pendingReviews = submissions.filter((s) => s.latest_eval_status === 'pending_review');
  const approvedCount = submissions.filter((s) => s.latest_eval_status === 'approved').length;

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Hola, {user?.full_name}
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {user?.role === 'teacher'
              ? 'Supervisa entregas, valida rúbricas y aprueba evaluaciones de las Cohortes 1 y 2.'
              : 'Gestiona tu portafolio de IA, evalúa tus laboratorios y explora tu mapa mental de competencias.'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            to="/portfolio"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold shadow-sm transition"
          >
            <FolderKanban className="w-4 h-4" />
            Ir al Portafolio
          </Link>
          <Link
            to="/mindmap"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-white hover:bg-slate-100 text-slate-800 border border-slate-200 text-sm font-semibold transition"
          >
            <Network className="w-4 h-4 text-indigo-600" />
            Mapa Mental IA
          </Link>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase">
            <span>Promedio Consolidado</span>
            <Award className="w-4 h-4 text-indigo-600" />
          </div>
          <p className="text-3xl font-bold text-slate-900 mt-2">
            {report?.overview?.overall_average ?? '—'} <span className="text-sm font-normal text-slate-400">/ 5.0</span>
          </p>
          <p className="text-xs text-slate-500 mt-1">
            C1: {report?.overview?.cohort_1_average ?? 'N/A'} · C2: {report?.overview?.cohort_2_average ?? 'N/A'}
          </p>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase">
            <span>Laboratorios Activos</span>
            <BookOpenCheck className="w-4 h-4 text-emerald-600" />
          </div>
          <p className="text-3xl font-bold text-slate-900 mt-2">{labs.length}</p>
          <p className="text-xs text-slate-500 mt-1">Distribuidos en Cohortes 1 y 2</p>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase">
            <span>Estado de Evaluaciones</span>
            <CheckCircle2 className="w-4 h-4 text-amber-500" />
          </div>
          <p className="text-3xl font-bold text-slate-900 mt-2">{approvedCount}</p>
          <p className="text-xs text-slate-500 mt-1">
            Aprobadas · <span className="text-amber-600 font-semibold">{pendingReviews.length} pendientes de revisión</span>
          </p>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase">
            <span>Motor IA & Sandbox</span>
            <Cpu className="w-4 h-4 text-sky-600" />
          </div>
          <p className="text-base font-bold text-slate-900 mt-2 truncate">
            {aiCfg?.provider?.toUpperCase()} / {aiCfg?.model_name}
          </p>
          <p className="text-xs mt-1">
            {aiCfg?.has_api_key ? (
              <span className="text-emerald-600 font-semibold">● API configurada · Sandbox activo</span>
            ) : (
              <Link to="/settings" className="text-amber-600 font-semibold underline">
                ● Configurar API Key gratuita
              </Link>
            )}
          </p>
        </div>
      </div>

      {/* Recent Submissions & Pending Teacher Approvals */}
      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
            <h2 className="font-bold text-slate-900 text-sm">Entregas y Evaluaciones Recientes</h2>
            <Link to="/portfolio" className="text-xs text-indigo-600 font-semibold hover:underline flex items-center gap-1">
              Ver portafolio completo <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
          <div className="divide-y divide-slate-100">
            {submissions.length === 0 ? (
              <p className="p-6 text-sm text-slate-500">Aún no hay entregas cargadas.</p>
            ) : (
              submissions.slice(0, 6).map((sub) => (
                <div key={sub.id} className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-slate-50/70">
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-bold px-2 py-0.5 rounded bg-indigo-50 text-indigo-700">
                        Cohorte {sub.cohort_number} · {sub.lab_code}
                      </span>
                      <span className="text-sm font-semibold text-slate-900">{sub.lab_title}</span>
                    </div>
                    <p className="text-xs text-slate-500 mt-1">
                      Estudiante: <strong>{sub.student_name}</strong> · Rúbrica v{sub.rubric_version_number} · PDF: {sub.pdf_filename}
                    </p>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    {sub.latest_grade != null && (
                      <span className="text-base font-bold text-slate-900">{sub.latest_grade}/5.0</span>
                    )}
                    <StatusBadge value={sub.latest_eval_status || sub.status} />
                    {sub.latest_evaluation_id && (
                      <Link
                        to={`/evaluations/${sub.latest_evaluation_id}`}
                        className="text-xs font-semibold text-indigo-600 hover:underline"
                      >
                        Ver detalle
                      </Link>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Quick Actions / Evolution Summary */}
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
            <h3 className="font-bold text-slate-900 text-sm mb-2 flex items-center gap-2">
              <FileBarChart2 className="w-4 h-4 text-indigo-600" />
              Evolución del Aprendizaje
            </h3>
            <p className="text-xs text-slate-600 leading-relaxed mb-4">
              {report?.overview?.evolution_trend || 'Sube y evalúa entregas de ambas cohortes para visualizar tu progreso.'}
            </p>
            <Link
              to="/report"
              className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold transition"
            >
              Abrir Informe Integrado + PDF
            </Link>
          </div>

          {user?.role === 'teacher' && pendingReviews.length > 0 && (
            <div className="bg-amber-50 rounded-xl border border-amber-200 p-5">
              <h3 className="font-bold text-amber-900 text-sm mb-2 flex items-center gap-2">
                <Clock className="w-4 h-4 text-amber-600" />
                Pendientes de Validación Docente ({pendingReviews.length})
              </h3>
              <div className="space-y-2">
                {pendingReviews.map((s) => (
                  <Link
                    key={s.id}
                    to={`/evaluations/${s.latest_evaluation_id}`}
                    className="block p-2.5 rounded-lg bg-white border border-amber-200 hover:border-amber-400 transition"
                  >
                    <p className="text-xs font-bold text-slate-900">{s.lab_code} — {s.student_name}</p>
                    <p className="text-[11px] text-amber-700 mt-0.5">
                      Nota preliminar: {s.latest_grade}/5.0 · Clic para revisar y aprobar
                    </p>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
