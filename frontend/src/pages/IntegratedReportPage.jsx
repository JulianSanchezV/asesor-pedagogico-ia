import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { Download, TrendingUp, Target, AlertTriangle, Compass, FileText } from 'lucide-react';
import { apiFetch } from '../api/client';
import { useAuth } from '../context/AuthContext';
import StatusBadge from '../components/StatusBadge';

export default function IntegratedReportPage() {
  const { user } = useAuth();
  const [students, setStudents] = useState([]);
  const [selectedStudentId, setSelectedStudentId] = useState('');
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    if (user?.role === 'teacher') {
      apiFetch('/api/auth/students').then((list) => {
        setStudents(list);
        if (list.length > 0) setSelectedStudentId(String(list[0].id));
      });
    }
  }, [user?.role]);

  useEffect(() => {
    setLoading(true);
    const query = user?.role === 'teacher' && selectedStudentId ? `?student_id=${selectedStudentId}` : '';
    apiFetch(`/api/reports/integrated${query}`)
      .then(setReport)
      .finally(() => setLoading(false));
  }, [selectedStudentId, user?.role]);

  const handleDownloadPdf = async () => {
    setDownloading(true);
    try {
      const query = user?.role === 'teacher' && selectedStudentId ? `?student_id=${selectedStudentId}` : '';
      const blob = await apiFetch(`/api/reports/integrated/pdf${query}`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `informe_integral_${report?.student?.full_name?.replace(/\s+/g, '_').toLowerCase() || 'ia'}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setDownloading(false);
    }
  };

  if (loading) return <div className="p-8 text-sm text-slate-500">Consolidando informe integral de aprendizaje...</div>;
  if (!report) return <div className="p-8 text-sm text-slate-500">No hay datos suficientes para generar el informe.</div>;

  const ov = report.overview;
  const chartData = report.lab_results.map((r) => ({
    name: `${r.lab_code} (C${r.cohort_number})`,
    nota: r.final_grade,
    cohort: r.cohort_number,
  }));

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Informe Integrado del Aprendizaje</h1>
          <p className="text-sm text-slate-500">
            Consolidado de Cohortes 1 y 2 para <strong>{report.student.full_name}</strong> ({report.student.email})
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {user?.role === 'teacher' && students.length > 0 && (
            <select
              value={selectedStudentId}
              onChange={(e) => setSelectedStudentId(e.target.value)}
              className="px-3 py-2 rounded-lg border border-slate-300 bg-white text-xs font-semibold"
            >
              {students.map((s) => (
                <option key={s.id} value={s.id}>{s.full_name}</option>
              ))}
            </select>
          )}
          <button
            onClick={handleDownloadPdf}
            disabled={downloading}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold shadow-sm cursor-pointer disabled:opacity-60"
          >
            <Download className="w-4 h-4" />
            {downloading ? 'Generando PDF...' : 'Descargar Informe PDF'}
          </button>
        </div>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs">
          <p className="text-[11px] uppercase font-bold text-slate-400">Promedio Global</p>
          <p className="text-3xl font-extrabold text-indigo-700 mt-1">{ov.overall_average}/5.0</p>
          <div className="mt-2"><StatusBadge value={ov.overall_mastery_level} /></div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs">
          <p className="text-[11px] uppercase font-bold text-slate-400">Cohorte 1</p>
          <p className="text-3xl font-extrabold text-slate-900 mt-1">{ov.cohort_1_average ?? 'N/A'}</p>
          <p className="text-xs text-slate-500 mt-1">Promedio de laboratorios</p>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs">
          <p className="text-[11px] uppercase font-bold text-slate-400">Cohorte 2</p>
          <p className="text-3xl font-extrabold text-slate-900 mt-1">{ov.cohort_2_average ?? 'N/A'}</p>
          <p className="text-xs text-slate-500 mt-1">Promedio de laboratorios</p>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs">
          <p className="text-[11px] uppercase font-bold text-slate-400">Cobertura</p>
          <p className="text-3xl font-extrabold text-slate-900 mt-1">
            {ov.labs_evaluated} <span className="text-base font-normal text-slate-400">/ {ov.total_labs_course}</span>
          </p>
          <p className="text-xs text-slate-500 mt-1">Laboratorios evaluados</p>
        </div>
      </div>

      {/* Evolution Banner & Chart */}
      <div className="grid lg:grid-cols-12 gap-6">
        <div className="lg:col-span-7 bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-bold text-slate-900 text-sm flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-indigo-600" />
              Evolución de Calificaciones (Cohortes 1 y 2)
            </h2>
            <span className="text-xs text-slate-500">Escala 0.0 – 5.0</span>
          </div>
          <p className="text-xs text-indigo-700 bg-indigo-50 border border-indigo-100 rounded-lg px-3 py-2 mb-4 font-medium">
            {ov.evolution_trend}
          </p>
          <div className="h-64">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, 5]} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="nota" radius={[6, 6, 0, 0]}>
                    {chartData.map((entry, idx) => (
                      <Cell key={idx} fill={entry.cohort === 1 ? '#4f46e5' : '#0f766e'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-slate-400">
                Evalúa al menos un laboratorio para ver la gráfica.
              </div>
            )}
          </div>
        </div>

        {/* Lab Summary List */}
        <div className="lg:col-span-5 bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-3">
          <h2 className="font-bold text-slate-900 text-sm flex items-center gap-2">
            <FileText className="w-4 h-4 text-slate-600" />
            Detalle por Laboratorio
          </h2>
          <div className="space-y-2.5 max-h-72 overflow-y-auto">
            {report.lab_results.map((r) => (
              <Link
                key={r.evaluation_id}
                to={`/evaluations/${r.evaluation_id}`}
                className="block p-3 rounded-xl border border-slate-200 hover:border-indigo-400 transition"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-indigo-700">C{r.cohort_number} · {r.lab_code}</span>
                  <span className="text-sm font-extrabold text-slate-900">{r.final_grade}/5.0</span>
                </div>
                <p className="text-xs font-semibold text-slate-800 mt-0.5">{r.lab_title}</p>
                <div className="flex items-center justify-between mt-2">
                  <StatusBadge value={r.status} />
                  <span className="text-[11px] text-slate-500">Sandbox: {r.sandbox_passed} OK / {r.sandbox_failed} Fail</span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </div>

      {/* Competencies & Gaps */}
      <div className="grid lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-3">
          <h2 className="font-bold text-slate-900 text-sm flex items-center gap-2">
            <Target className="w-4 h-4 text-emerald-600" />
            Competencias Adquiridas y Niveles de Dominio
          </h2>
          <div className="space-y-3">
            {report.competencies.map((comp, i) => (
              <div key={i} className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="text-sm font-bold text-slate-900">{comp.topic}</p>
                    <p className="text-[11px] text-slate-500">{comp.category}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-indigo-700">{comp.mastery_score}/5.0</span>
                    <StatusBadge value={comp.mastery_level} />
                  </div>
                </div>
                <div className="w-full bg-slate-200 h-2 rounded-full mt-2 overflow-hidden">
                  <div
                    className="h-full bg-indigo-600 rounded-full"
                    style={{ width: `${Math.min(100, (comp.mastery_score / 5) * 100)}%` }}
                  />
                </div>
                <p className="text-xs text-slate-600 mt-2">{comp.evidences[0]}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Personalized Strengthening Plan */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
          <h2 className="font-bold text-slate-900 text-sm flex items-center gap-2">
            <Compass className="w-4 h-4 text-amber-600" />
            Brechas Identificadas y Plan Personalizado de Fortalecimiento
          </h2>
          <div className="space-y-3">
            {report.strengthening_plan.map((step) => (
              <div key={step.step} className="p-4 rounded-xl border border-amber-200 bg-amber-50/40 space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-900">
                    Paso {step.step}: {step.topic}
                  </span>
                  <span
                    className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full ${
                      step.priority === 'Alta'
                        ? 'bg-rose-100 text-rose-800'
                        : step.priority === 'Media'
                        ? 'bg-amber-100 text-amber-800'
                        : 'bg-emerald-100 text-emerald-800'
                    }`}
                  >
                    Prioridad {step.priority}
                  </span>
                </div>
                <p className="text-xs text-slate-700 flex items-start gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0 mt-0.5" />
                  <span>{step.action}</span>
                </p>
                <p className="text-[11px] text-slate-600 pl-5">
                  <strong>Acción práctica:</strong> {step.suggested_practice}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
