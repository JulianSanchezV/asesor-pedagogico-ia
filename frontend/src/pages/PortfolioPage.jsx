import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  FileText,
  FolderArchive,
  Github,
  Play,
  UploadCloud,
  Video,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Trash2,
  Clock,
  Cpu,
} from 'lucide-react';
import { apiFetch } from '../api/client';
import { useAuth } from '../context/AuthContext';
import StatusBadge from '../components/StatusBadge';

export default function PortfolioPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [cohorts, setCohorts] = useState([]);
  const [labs, setLabs] = useState([]);
  const [students, setStudents] = useState([]);
  const [submissions, setSubmissions] = useState([]);
  const [cohortFilter, setCohortFilter] = useState('all');
  const [studentFilter, setStudentFilter] = useState('all');

  // Upload form
  const [selectedCohortId, setSelectedCohortId] = useState('');
  const [labId, setLabId] = useState('');
  const [codeSourceType, setCodeSourceType] = useState('none');
  const [githubUrl, setGithubUrl] = useState('');
  const [pdfFile, setPdfFile] = useState(null);
  const [zipFile, setZipFile] = useState(null);
  const [mediaUrl, setMediaUrl] = useState('');
  const [mediaNotes, setMediaNotes] = useState('');
  const [uploading, setUploading] = useState(false);
  const [evaluatingId, setEvaluatingId] = useState(null);
  const [evalProgress, setEvalProgress] = useState(null);
  const [feedback, setFeedback] = useState({ type: '', text: '' });

  const loadData = async () => {
    const reqs = [
      apiFetch('/api/labs/cohorts'),
      apiFetch('/api/labs'),
      apiFetch('/api/submissions'),
    ];
    if (user?.role === 'teacher') {
      reqs.push(apiFetch('/api/auth/students').catch(() => []));
    }
    const [cohortsData, labsData, subsData, studentsData] = await Promise.all(reqs);
    setCohorts(cohortsData);
    setLabs(labsData);
    setSubmissions(subsData);
    if (studentsData) setStudents(studentsData);

    const activeCohortId = selectedCohortId || (cohortsData[0] ? String(cohortsData[0].id) : '');
    if (activeCohortId && !selectedCohortId) {
      setSelectedCohortId(activeCohortId);
    }
    const labsInCohort = labsData.filter((l) => String(l.cohort_id) === String(activeCohortId));
    if (labsInCohort.length > 0 && !labsInCohort.some((l) => String(l.id) === String(labId))) {
      setLabId(String(labsInCohort[0].id));
    } else if (labsInCohort.length === 0) {
      setLabId('');
    }
  };

  useEffect(() => {
    loadData();
  }, [user?.role]);

  const labsForSelectedCohort = labs.filter((l) => String(l.cohort_id) === String(selectedCohortId));

  const handleCohortChange = (newCohortId) => {
    setSelectedCohortId(newCohortId);
    const matchingLabs = labs.filter((l) => String(l.cohort_id) === String(newCohortId));
    setLabId(matchingLabs.length > 0 ? String(matchingLabs[0].id) : '');
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    setFeedback({ type: '', text: '' });
    if (!labId) {
      setFeedback({
        type: 'err',
        text: 'No hay un laboratorio seleccionado en esta cohorte. Crea primero un laboratorio con su rúbrica en "Laboratorios y Rúbricas".',
      });
      return;
    }
    if (!pdfFile) {
      setFeedback({ type: 'err', text: 'Debes adjuntar el informe en PDF o DOCX de texto legible.' });
      return;
    }
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('lab_id', labId);
      const effectiveCodeType =
        codeSourceType === 'zip' && !zipFile
          ? 'none'
          : codeSourceType === 'github' && !githubUrl.trim()
          ? 'none'
          : codeSourceType;
      fd.append('code_source_type', effectiveCodeType);
      fd.append('pdf_file', pdfFile);
      if (effectiveCodeType === 'zip' && zipFile) {
        fd.append('code_zip', zipFile);
      } else if (effectiveCodeType === 'github') {
        fd.append('github_url', githubUrl.trim());
      }
      if (mediaUrl.trim()) fd.append('optional_media_url', mediaUrl.trim());
      if (mediaNotes.trim()) fd.append('optional_media_notes', mediaNotes.trim());

      await apiFetch('/api/submissions', { method: 'POST', body: fd });
      setPdfFile(null);
      setZipFile(null);
      setGithubUrl('');
      setMediaUrl('');
      setMediaNotes('');
      await loadData();
      setFeedback({
        type: 'ok',
        text: 'Entrega registrada en el portafolio conservando la versión activa de la rúbrica. Ya puedes ejecutar la evaluación inteligente.',
      });
    } catch (err) {
      setFeedback({ type: 'err', text: err.message });
    } finally {
      setUploading(false);
    }
  };

  const handleEvaluate = async (sub) => {
    const subId = sub.id;
    setEvaluatingId(subId);
    setFeedback({ type: '', text: '' });
    setEvalProgress({
      lab_label: `${sub.lab_code} — ${sub.lab_title}`,
      percent: 5,
      elapsed_seconds: 0,
      detail: `Iniciando evaluación de "${sub.pdf_filename}"...`,
      steps: [
        { id: 'pdf', label: '1. Leyendo informe técnico (PDF/DOCX)', state: 'active', note: sub.pdf_filename },
        { id: 'sandbox', label: '2. Verificación objetiva de código en Sandbox', state: 'pending', note: '' },
        { id: 'ai', label: '3. Analizando evidencias con modelo de IA', state: 'pending', note: '' },
        { id: 'grade', label: '4. Cálculo de nota en Backend y trazabilidad', state: 'pending', note: '' },
      ],
    });

    const pollTimer = setInterval(async () => {
      try {
        const prog = await apiFetch(`/api/evaluations/progress/${subId}`);
        if (prog && prog.status !== 'idle') {
          setEvalProgress(prog);
        }
      } catch {
        // ignore transient polling error
      }
    }, 650);

    try {
      const ev = await apiFetch(`/api/evaluations/run/${subId}`, { method: 'POST' });
      clearInterval(pollTimer);
      setEvalProgress(null);
      navigate(`/evaluations/${ev.id}`);
    } catch (err) {
      clearInterval(pollTimer);
      setEvalProgress(null);
      setFeedback({ type: 'err', text: err.message });
    } finally {
      setEvaluatingId(null);
    }
  };

  const handleDeleteSubmission = async (sub) => {
    const ok = window.confirm(`¿Eliminar la entrega de "${sub.lab_code} - ${sub.pdf_filename}"?`);
    if (!ok) return;
    setFeedback({ type: '', text: '' });
    try {
      await apiFetch(`/api/submissions/${sub.id}`, { method: 'DELETE' });
      await loadData();
      setFeedback({ type: 'ok', text: 'Entrega eliminada del portafolio.' });
    } catch (err) {
      setFeedback({ type: 'err', text: err.message });
    }
  };

  const filteredSubs = submissions.filter((s) => {
    const matchCohort = cohortFilter === 'all' ? true : String(s.cohort_number) === cohortFilter;
    const matchStudent = studentFilter === 'all' ? true : String(s.student_id) === studentFilter;
    return matchCohort && matchStudent;
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Portafolio Académico (Cohortes 1 y 2)</h1>
        <p className="text-sm text-slate-500">
          Carga tu informe en PDF legible, tu código fuente (ZIP o GitHub) y ejecuta la evaluación inteligente verificada en sandbox.
        </p>
      </div>

      {feedback.text && (
        <div
          className={`p-3.5 rounded-xl border text-xs font-medium flex items-center gap-2 ${
            feedback.type === 'ok'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : 'bg-rose-50 border-rose-200 text-rose-800'
          }`}
        >
          {feedback.type === 'ok' ? <CheckCircle2 className="w-4 h-4 shrink-0" /> : <AlertCircle className="w-4 h-4 shrink-0" />}
          <span>{feedback.text}</span>
        </div>
      )}

      {/* Upload Form */}
      <form onSubmit={handleUpload} className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs space-y-4">
        <h2 className="font-bold text-slate-900 text-sm flex items-center gap-2">
          <UploadCloud className="w-4 h-4 text-indigo-600" />
          Cargar Nueva Entrega de Laboratorio
        </h2>

        <div className="grid md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Cohorte</label>
            <select
              value={selectedCohortId}
              onChange={(e) => handleCohortChange(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white"
            >
              {cohorts.length === 0 ? (
                <option value="">Cargando cohortes...</option>
              ) : (
                cohorts.map((c) => (
                  <option key={c.id} value={String(c.id)}>
                    {c.name}
                  </option>
                ))
              )}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Laboratorio</label>
            <select
              value={labId}
              disabled={labsForSelectedCohort.length === 0}
              onChange={(e) => setLabId(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white disabled:bg-slate-100 disabled:text-slate-500"
            >
              {labsForSelectedCohort.length === 0 ? (
                <option value="">Sin laboratorios en esta cohorte</option>
              ) : (
                labsForSelectedCohort.map((lab) => (
                  <option key={lab.id} value={String(lab.id)}>
                    {lab.code} — {lab.title} (Rúbrica v{lab.active_rubric_version || 'sin rúbrica'})
                  </option>
                ))
              )}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Informe Técnico (PDF recomendado, también .docx/.txt)</label>
            <input
              type="file"
              accept=".pdf,.docx,.txt,.md"
              required
              onChange={(e) => setPdfFile(e.target.files?.[0] || null)}
              className="w-full text-xs file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:bg-indigo-50 file:text-indigo-700 file:font-semibold border border-slate-300 rounded-lg p-1"
            />
          </div>
        </div>

        {labsForSelectedCohort.length === 0 && (
          <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-800 flex flex-wrap items-center justify-between gap-2">
            <span>
              Todavía no hay laboratorios creados en esta cohorte.{' '}
              {user?.role === 'teacher'
                ? 'Crea primero el laboratorio y su rúbrica (100 %) para poder subir entregas.'
                : 'El docente debe crear primero el laboratorio y su rúbrica (100 %) en "Laboratorios y Rúbricas".'}
            </span>
            <Link to="/labs" className="font-bold underline text-amber-900">
              Ir a Laboratorios y Rúbricas →
            </Link>
          </div>
        )}

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Origen del Código Fuente <span className="text-slate-400 font-normal">(Opcional)</span>
            </label>
            <div className="flex gap-2 mb-2">
              <button
                type="button"
                onClick={() => { setCodeSourceType('none'); setZipFile(null); setGithubUrl(''); }}
                className={`flex-1 py-2 px-2.5 rounded-lg text-xs font-semibold border flex items-center justify-center gap-1 cursor-pointer ${
                  codeSourceType === 'none' ? 'bg-indigo-50 border-indigo-500 text-indigo-700' : 'border-slate-200 text-slate-600'
                }`}
              >
                Sin código
              </button>
              <button
                type="button"
                onClick={() => setCodeSourceType('zip')}
                className={`flex-1 py-2 px-2.5 rounded-lg text-xs font-semibold border flex items-center justify-center gap-1.5 cursor-pointer ${
                  codeSourceType === 'zip' ? 'bg-indigo-50 border-indigo-500 text-indigo-700' : 'border-slate-200 text-slate-600'
                }`}
              >
                <FolderArchive className="w-3.5 h-3.5" /> Archivo ZIP
              </button>
              <button
                type="button"
                onClick={() => setCodeSourceType('github')}
                className={`flex-1 py-2 px-2.5 rounded-lg text-xs font-semibold border flex items-center justify-center gap-1.5 cursor-pointer ${
                  codeSourceType === 'github' ? 'bg-indigo-50 border-indigo-500 text-indigo-700' : 'border-slate-200 text-slate-600'
                }`}
              >
                <Github className="w-3.5 h-3.5" /> GitHub
              </button>
            </div>
            {codeSourceType === 'none' && (
              <p className="text-[11px] text-slate-500 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2">
                Solo se evaluará el informe técnico cargado. Si tu laboratorio incluye código, selecciona ZIP o GitHub.
              </p>
            )}
            {codeSourceType === 'zip' && (
              <input
                type="file"
                accept=".zip"
                onChange={(e) => setZipFile(e.target.files?.[0] || null)}
                className="w-full text-xs file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:bg-slate-100 file:text-slate-700 file:font-semibold border border-slate-300 rounded-lg p-1"
              />
            )}
            {codeSourceType === 'github' && (
              <input
                type="url"
                value={githubUrl}
                onChange={(e) => setGithubUrl(e.target.value)}
                placeholder="https://github.com/usuario/repositorio-lab"
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
              />
            )}
          </div>

          <div className="space-y-2">
            <label className="block text-xs font-semibold text-slate-700">
              Video o Presentación <span className="text-slate-400 font-normal">(Opcional)</span>
            </label>
            <input
              type="url"
              value={mediaUrl}
              onChange={(e) => setMediaUrl(e.target.value)}
              placeholder="Enlace a video sustentación o diapositivas (opcional)"
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs"
            />
            <input
              type="text"
              value={mediaNotes}
              onChange={(e) => setMediaNotes(e.target.value)}
              placeholder="Notas adicionales sobre evidencias multimedia (opcional)"
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs"
            />
          </div>
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={uploading}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold disabled:opacity-60 cursor-pointer"
          >
            {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <UploadCloud className="w-4 h-4" />}
            {uploading ? 'Subiendo evidencias...' : 'Guardar en Portafolio'}
          </button>
        </div>
      </form>

      {/* Submissions Table / Cards by Cohort */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200 flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-bold text-slate-900 text-sm">Entregas Registradas ({filteredSubs.length})</h2>
          <div className="flex flex-wrap items-center gap-2">
            {user?.role === 'teacher' && students.length > 0 && (
              <select
                value={studentFilter}
                onChange={(e) => setStudentFilter(e.target.value)}
                className="px-2.5 py-1 rounded-lg border border-slate-300 bg-white text-xs font-semibold text-slate-700"
              >
                <option value="all">Todos los estudiantes</option>
                {students.map((st) => (
                  <option key={st.id} value={String(st.id)}>
                    {st.full_name}
                  </option>
                ))}
              </select>
            )}
            <div className="flex gap-1.5">
              {['all', '1', '2'].map((c) => (
                <button
                  key={c}
                  onClick={() => setCohortFilter(c)}
                  className={`px-3 py-1 rounded-lg text-xs font-semibold cursor-pointer ${
                    cohortFilter === c ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {c === 'all' ? 'Todas' : `Cohorte ${c}`}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="divide-y divide-slate-100">
          {filteredSubs.length === 0 ? (
            <p className="p-6 text-sm text-slate-500">No hay entregas en esta cohorte todavía.</p>
          ) : (
            filteredSubs.map((sub) => (
              <div key={sub.id} className="p-5 flex flex-col lg:flex-row lg:items-center justify-between gap-4 hover:bg-slate-50/70">
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="px-2 py-0.5 rounded bg-indigo-100 text-indigo-800 text-xs font-bold">
                      Cohorte {sub.cohort_number} · {sub.lab_code}
                    </span>
                    <span className="font-bold text-sm text-slate-900">{sub.lab_title}</span>
                    <StatusBadge value={sub.latest_eval_status || sub.status} />
                  </div>
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-600">
                    <span>Estudiante: <strong>{sub.student_name}</strong></span>
                    <span className="inline-flex items-center gap-1">
                      <FileText className="w-3.5 h-3.5 text-slate-400" />
                      {sub.pdf_filename} ({sub.pdf_page_count} pág.)
                    </span>
                    <span className="inline-flex items-center gap-1">
                      {sub.code_source_type === 'github' ? (
                        <><Github className="w-3.5 h-3.5" /> {sub.github_url}</>
                      ) : sub.code_source_type === 'zip' ? (
                        <><FolderArchive className="w-3.5 h-3.5" /> {sub.code_filename}</>
                      ) : (
                        <span className="text-slate-400">Solo informe (sin código)</span>
                      )}
                    </span>
                    <span>Rúbrica preservada: <strong>v{sub.rubric_version_number}</strong></span>
                    {sub.optional_media_url && (
                      <a href={sub.optional_media_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-indigo-600 hover:underline">
                        <Video className="w-3.5 h-3.5" /> Media opcional
                      </a>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2.5 shrink-0">
                  {sub.latest_grade != null && (
                    <div className="text-right mr-2">
                      <p className="text-[10px] uppercase text-slate-400 font-bold">Nota</p>
                      <p className="text-lg font-extrabold text-slate-900">{sub.latest_grade} / 5.0</p>
                    </div>
                  )}
                  {sub.latest_evaluation_id && (
                    <Link
                      to={`/evaluations/${sub.latest_evaluation_id}`}
                      className="px-3.5 py-2 rounded-lg border border-slate-300 hover:bg-slate-100 text-xs font-semibold text-slate-800"
                    >
                      Ver Evaluación
                    </Link>
                  )}
                  <button
                    type="button"
                    disabled={evaluatingId === sub.id}
                    onClick={() => handleEvaluate(sub)}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold disabled:opacity-60 cursor-pointer"
                  >
                    {evaluatingId === sub.id ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" /> Analizando en Sandbox + IA...
                      </>
                    ) : (
                      <>
                        <Play className="w-3.5 h-3.5" /> {sub.latest_evaluation_id ? 'Re-evaluar' : 'Evaluar con IA'}
                      </>
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDeleteSubmission(sub)}
                    title="Eliminar entrega"
                    className="p-2 rounded-lg border border-slate-200 text-slate-400 hover:text-rose-600 hover:border-rose-200 hover:bg-rose-50 cursor-pointer"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
      {/* Live Evaluation Progress Modal */}
      {evaluatingId && evalProgress && (
        <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-white rounded-2xl shadow-2xl border border-slate-200 p-6 space-y-5">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-indigo-100 text-indigo-700 flex items-center justify-center shrink-0">
                  <Cpu className="w-5 h-5 animate-pulse" />
                </div>
                <div>
                  <h3 className="font-bold text-slate-900 text-base">Evaluación en Progreso</h3>
                  <p className="text-xs text-slate-500">{evalProgress.lab_label}</p>
                </div>
              </div>
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-slate-100 text-slate-700 text-xs font-mono font-bold">
                <Clock className="w-3.5 h-3.5 text-slate-500" />
                {String(Math.floor((evalProgress.elapsed_seconds || 0) / 60)).padStart(2, '0')}:
                {String((evalProgress.elapsed_seconds || 0) % 60).padStart(2, '0')}
              </span>
            </div>

            {/* Progress Bar */}
            <div>
              <div className="flex justify-between text-xs font-semibold mb-1.5">
                <span className="text-indigo-700">Avance del pipeline</span>
                <span className="text-slate-700">{evalProgress.percent || 0}%</span>
              </div>
              <div className="w-full h-2.5 bg-slate-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-indigo-600 rounded-full transition-all duration-500"
                  style={{ width: `${Math.max(6, evalProgress.percent || 0)}%` }}
                />
              </div>
            </div>

            {/* Step-by-step live list */}
            <div className="space-y-2.5">
              {(evalProgress.steps || []).map((step) => (
                <div
                  key={step.id}
                  className={`flex items-center justify-between gap-2 p-3 rounded-xl border text-xs transition ${
                    step.state === 'done'
                      ? 'bg-emerald-50/70 border-emerald-200 text-emerald-900'
                      : step.state === 'active'
                      ? 'bg-indigo-50 border-indigo-300 text-indigo-950 shadow-xs'
                      : 'bg-slate-50 border-slate-200 text-slate-400'
                  }`}
                >
                  <div className="flex items-center gap-2.5 font-semibold">
                    {step.state === 'done' ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                    ) : step.state === 'active' ? (
                      <Loader2 className="w-4 h-4 text-indigo-600 animate-spin shrink-0" />
                    ) : (
                      <Clock className="w-4 h-4 text-slate-300 shrink-0" />
                    )}
                    <span>{step.label}</span>
                  </div>
                  {step.note && (
                    <span className="text-[11px] font-normal opacity-80 truncate max-w-[160px]" title={step.note}>
                      {step.note}
                    </span>
                  )}
                </div>
              ))}
            </div>

            {/* Exact current activity message */}
            <div className="p-3.5 rounded-xl bg-slate-900 text-slate-100 text-xs font-mono leading-relaxed">
              <span className="text-emerald-400 font-bold">› </span>
              {evalProgress.detail}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
