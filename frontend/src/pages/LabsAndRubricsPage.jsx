import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  FileUp,
  History,
  Plus,
  Sparkles,
  Trash2,
  Save,
  Loader2,
} from 'lucide-react';
import { apiFetch } from '../api/client';
import { useAuth } from '../context/AuthContext';

const DEFAULT_LEVELS = [
  { level: 'excelente', label: 'Excelente (4.5 - 5.0)', score_ratio: 1.0, descriptor: 'Domina completamente el criterio con evidencias verificables.' },
  { level: 'sobresaliente', label: 'Sobresaliente (3.8 - 4.4)', score_ratio: 0.85, descriptor: 'Cumple adecuadamente con observaciones menores.' },
  { level: 'aceptable', label: 'Aceptable (3.0 - 3.7)', score_ratio: 0.68, descriptor: 'Cumple los mínimos esperados con brechas identificables.' },
  { level: 'insuficiente', label: 'Insuficiente (< 3.0)', score_ratio: 0.35, descriptor: 'No evidencia dominio suficiente o presenta fallos graves.' },
];

export default function LabsAndRubricsPage() {
  const { user } = useAuth();
  const [cohorts, setCohorts] = useState([]);
  const [labs, setLabs] = useState([]);
  const [selectedLab, setSelectedLab] = useState(null);
  const [rubricVersions, setRubricVersions] = useState([]);
  const [showNewLab, setShowNewLab] = useState(false);

  // New lab form
  const [newLab, setNewLab] = useState({
    cohort_id: 1,
    code: '',
    title: '',
    description: '',
    objectivesText: '',
    topicsText: '',
  });

  // Rubric editor state
  const [rubricTitle, setRubricTitle] = useState('');
  const [criteria, setCriteria] = useState([]);
  const [rawRubricText, setRawRubricText] = useState('');
  const [validation, setValidation] = useState(null);
  const [msg, setMsg] = useState({ type: '', text: '' });
  const [busy, setBusy] = useState(false);
  const [parsingLabDoc, setParsingLabDoc] = useState(false);
  const [labDocNotice, setLabDocNotice] = useState('');

  const loadLabs = async () => {
    const [cData, lData] = await Promise.all([apiFetch('/api/labs/cohorts'), apiFetch('/api/labs')]);
    setCohorts(cData);
    setLabs(lData);
    if (cData.length > 0) {
      setNewLab((prev) => ({
        ...prev,
        cohort_id: cData.some((c) => String(c.id) === String(prev.cohort_id)) ? prev.cohort_id : cData[0].id,
      }));
    }
    if (lData.length > 0 && !selectedLab) {
      setSelectedLab(lData[0]);
    }
  };

  useEffect(() => {
    loadLabs();
  }, []);

  useEffect(() => {
    if (!selectedLab) return;
    apiFetch(`/api/rubrics/lab/${selectedLab.id}`).then((versions) => {
      setRubricVersions(versions);
      if (versions.length > 0) {
        const active = versions.find((v) => v.is_active) || versions[0];
        setRubricTitle(active.title);
        setCriteria(active.criteria);
      } else {
        setRubricTitle(`Rúbrica ${selectedLab.code}`);
        setCriteria([
          { id: 'c1', name: 'Dominio conceptual de IA', competency: 'Aplicación teórica', weight_percent: 40, levels: DEFAULT_LEVELS },
          { id: 'c2', name: 'Implementación técnica y pruebas', competency: 'Ingeniería de software IA', weight_percent: 35, levels: DEFAULT_LEVELS },
          { id: 'c3', name: 'Análisis de resultados en informe', competency: 'Comunicación científica', weight_percent: 25, levels: DEFAULT_LEVELS },
        ]);
      }
      setValidation(null);
      setMsg({ type: '', text: '' });
    });
  }, [selectedLab?.id]);

  const totalWeight = Math.round(criteria.reduce((acc, c) => acc + (Number(c.weight_percent) || 0), 0) * 100) / 100;
  const isSum100 = Math.abs(totalWeight - 100) < 0.01;

  const handleParseLabDocument = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setParsingLabDoc(true);
    setLabDocNotice('');
    setMsg({ type: '', text: '' });
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('cohort_id', String(newLab.cohort_id));
      const res = await apiFetch('/api/labs/parse-document', { method: 'POST', body: fd });
      const d = res.draft;
      setNewLab((prev) => ({
        ...prev,
        code: d.code || prev.code,
        title: d.title || prev.title,
        description: d.description || prev.description,
        objectivesText: (d.objectives || []).join('\n'),
        topicsText: (d.ai_topics || []).join(', '),
      }));
      setLabDocNotice(
        `Documento "${res.filename}" (${res.word_count} palabras) analizado con ${res.parsed_by}. Revisa los campos y haz clic en Guardar Laboratorio.`
      );
    } catch (err) {
      setMsg({ type: 'err', text: err.message });
    } finally {
      setParsingLabDoc(false);
      e.target.value = '';
    }
  };

  const handleCreateLab = async (e) => {
    e.preventDefault();
    setMsg({ type: '', text: '' });
    try {
      const created = await apiFetch('/api/labs', {
        method: 'POST',
        body: JSON.stringify({
          cohort_id: Number(newLab.cohort_id),
          code: newLab.code,
          title: newLab.title,
          description: newLab.description,
          objectives: newLab.objectivesText.split('\n').map((s) => s.trim()).filter(Boolean),
          ai_topics: newLab.topicsText.split(',').map((s) => s.trim()).filter(Boolean),
        }),
      });
      setShowNewLab(false);
      setNewLab({ cohort_id: 1, code: '', title: '', description: '', objectivesText: '', topicsText: '' });
      setLabDocNotice('');
      await loadLabs();
      setSelectedLab(created);
      setMsg({ type: 'ok', text: `Laboratorio ${created.code} creado correctamente.` });
    } catch (err) {
      setMsg({ type: 'err', text: err.message });
    }
  };

  const handleValidate = async () => {
    const res = await apiFetch('/api/rubrics/validate', {
      method: 'POST',
      body: JSON.stringify({ criteria }),
    });
    setValidation(res);
    return res;
  };

  const handleSaveRubric = async () => {
    setMsg({ type: '', text: '' });
    setBusy(true);
    try {
      const check = await handleValidate();
      if (!check.is_valid) {
        setMsg({ type: 'err', text: 'Corrige las inconsistencias detectadas antes de guardar la rúbrica.' });
        return;
      }
      const saved = await apiFetch('/api/rubrics', {
        method: 'POST',
        body: JSON.stringify({
          lab_id: selectedLab.id,
          title: rubricTitle,
          criteria: criteria.map((c) => ({ ...c, weight_percent: Number(c.weight_percent) })),
        }),
      });
      const versions = await apiFetch(`/api/rubrics/lab/${selectedLab.id}`);
      setRubricVersions(versions);
      setMsg({ type: 'ok', text: `Rúbrica guardada como versión v${saved.version_number} (100 % validada).` });
    } catch (err) {
      setMsg({ type: 'err', text: err.message });
    } finally {
      setBusy(false);
    }
  };

  const handleParseText = async () => {
    if (!rawRubricText.trim()) return;
    setBusy(true);
    setMsg({ type: '', text: '' });
    try {
      const res = await apiFetch('/api/rubrics/parse', {
        method: 'POST',
        body: JSON.stringify({ raw_text: rawRubricText, lab_title: selectedLab?.title || '' }),
      });
      setRubricTitle(res.draft.title);
      setCriteria(res.draft.criteria);
      setValidation(res.validation);
      setMsg({
        type: res.validation.is_valid ? 'ok' : 'err',
        text: `Rúbrica interpretada (${res.parsed_by}). ${
          res.validation.is_valid ? 'Suma 100 % correctamente.' : 'Se detectaron inconsistencias que debes corregir antes de guardar.'
        }`,
      });
    } catch (err) {
      setMsg({ type: 'err', text: err.message });
    } finally {
      setBusy(false);
    }
  };

  const handleParsePdf = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setMsg({ type: '', text: '' });
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('lab_title', selectedLab?.title || '');
      const res = await apiFetch('/api/rubrics/parse-pdf', { method: 'POST', body: fd });
      setRubricTitle(res.draft.title);
      setCriteria(res.draft.criteria);
      setValidation(res.validation);
      setMsg({ type: 'ok', text: `Rúbrica extraída desde PDF (${res.parsed_by}). Revisa ponderaciones y guarda.` });
    } catch (err) {
      setMsg({ type: 'err', text: err.message });
    } finally {
      setBusy(false);
      e.target.value = '';
    }
  };

  const addCriterion = () => {
    const nextIdx = criteria.length + 1;
    setCriteria([
      ...criteria,
      {
        id: `c${nextIdx}`,
        name: `Nuevo criterio ${nextIdx}`,
        competency: 'Competencia de IA',
        weight_percent: 10,
        levels: DEFAULT_LEVELS,
      },
    ]);
  };

  const updateCriterion = (idx, field, value) => {
    const copy = [...criteria];
    copy[idx] = { ...copy[idx], [field]: value };
    setCriteria(copy);
  };

  const removeCriterion = (idx) => {
    setCriteria(criteria.filter((_, i) => i !== idx));
  };

  const handleDeleteLab = async (labToDelete) => {
    const ok = window.confirm(
      `¿Eliminar el laboratorio "${labToDelete.code} - ${labToDelete.title}" junto con sus rúbricas y entregas asociadas?`
    );
    if (!ok) return;
    setMsg({ type: '', text: '' });
    try {
      await apiFetch(`/api/labs/${labToDelete.id}`, { method: 'DELETE' });
      const [cData, lData] = await Promise.all([apiFetch('/api/labs/cohorts'), apiFetch('/api/labs')]);
      setCohorts(cData);
      setLabs(lData);
      setSelectedLab(lData.length > 0 ? lData[0] : null);
      setMsg({ type: 'ok', text: `Laboratorio ${labToDelete.code} eliminado correctamente.` });
    } catch (err) {
      setMsg({ type: 'err', text: err.message });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Laboratorios y Gestión de Rúbricas</h1>
          <p className="text-sm text-slate-500">
            Define descripción, objetivos y rúbricas parametrizadas con validación estricta del 100 % y versionamiento inmutable.
          </p>
        </div>
        {user?.role === 'teacher' && (
          <button
            onClick={() => setShowNewLab(!showNewLab)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold cursor-pointer"
          >
            <Plus className="w-4 h-4" /> Nuevo Laboratorio
          </button>
        )}
      </div>

      {showNewLab && (
        <form onSubmit={handleCreateLab} className="bg-white rounded-xl border border-indigo-200 p-5 space-y-4 shadow-xs">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-bold text-slate-900 text-sm">Crear Laboratorio en Cohorte 1 o 2</h2>
            <span className="text-xs text-slate-500">Sube el archivo guía y la IA llenará los campos automáticamente</span>
          </div>

          {/* Document Upload + AI Analysis Box */}
          <div className="p-4 rounded-xl border-2 border-dashed border-indigo-300 bg-indigo-50/50 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="space-y-0.5">
              <p className="text-xs font-bold text-indigo-900 flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-indigo-600" />
                Importar Laboratorio desde Documento (PDF, Word .docx, TXT o MD)
              </p>
              <p className="text-[11px] text-indigo-700">
                Sube el documento del laboratorio para que la IA extraiga título, descripción, objetivos y temáticas de IA.
              </p>
            </div>
            <label className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold cursor-pointer shrink-0 shadow-xs">
              {parsingLabDoc ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" /> Analizando con IA...
                </>
              ) : (
                <>
                  <FileUp className="w-4 h-4" /> Subir Documento y Analizar
                </>
              )}
              <input
                type="file"
                accept=".pdf,.docx,.txt,.md"
                disabled={parsingLabDoc}
                className="hidden"
                onChange={handleParseLabDocument}
              />
            </label>
          </div>

          {labDocNotice && (
            <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 font-medium flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>{labDocNotice}</span>
            </div>
          )}
          <div className="grid sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Cohorte</label>
              <select
                value={newLab.cohort_id}
                onChange={(e) => setNewLab({ ...newLab, cohort_id: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white"
              >
                {cohorts.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Código</label>
              <input
                required
                placeholder="Ej. LAB-2.3"
                value={newLab.code}
                onChange={(e) => setNewLab({ ...newLab, code: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Título</label>
              <input
                required
                placeholder="Ej. Visión Artificial con CNN"
                value={newLab.title}
                onChange={(e) => setNewLab({ ...newLab, title: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Descripción del laboratorio</label>
            <textarea
              required
              rows={2}
              value={newLab.description}
              onChange={(e) => setNewLab({ ...newLab, description: e.target.value })}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
            />
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Objetivos (uno por línea)</label>
              <textarea
                rows={3}
                value={newLab.objectivesText}
                onChange={(e) => setNewLab({ ...newLab, objectivesText: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Temáticas IA (separadas por coma)</label>
              <input
                placeholder="CNN, Transfer Learning, Métricas de Visión"
                value={newLab.topicsText}
                onChange={(e) => setNewLab({ ...newLab, topicsText: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
              />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setShowNewLab(false)} className="px-3 py-1.5 text-sm text-slate-600">
              Cancelar
            </button>
            <button type="submit" className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-semibold cursor-pointer">
              Guardar Laboratorio
            </button>
          </div>
        </form>
      )}

      <div className="grid lg:grid-cols-12 gap-6">
        {/* Left List of Labs by Cohort */}
        <div className="lg:col-span-4 space-y-4">
          {cohorts.map((cohort) => (
            <div key={cohort.id} className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs">
              <div className="px-4 py-3 bg-slate-900 text-white">
                <p className="text-sm font-bold">{cohort.name}</p>
              </div>
              <div className="divide-y divide-slate-100">
                {labs.filter((l) => l.cohort_id === cohort.id).length === 0 ? (
                  <p className="p-3.5 text-xs text-slate-400 italic">Sin laboratorios todavía</p>
                ) : (
                  labs
                    .filter((l) => l.cohort_id === cohort.id)
                    .map((lab) => (
                      <button
                        key={lab.id}
                        onClick={() => setSelectedLab(lab)}
                        className={`w-full text-left p-3.5 transition cursor-pointer ${
                          selectedLab?.id === lab.id ? 'bg-indigo-50 border-l-4 border-indigo-600' : 'hover:bg-slate-50'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-indigo-700">{lab.code}</span>
                          <span className="text-[11px] text-slate-500">
                            {lab.active_rubric_version ? `Rúbrica v${lab.active_rubric_version}` : 'Sin rúbrica'}
                          </span>
                        </div>
                        <p className="text-sm font-semibold text-slate-900 mt-0.5">{lab.title}</p>
                      </button>
                    ))
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Right Lab Detail & Rubric Builder */}
        {!selectedLab ? (
          <div className="lg:col-span-8 bg-white rounded-xl border border-slate-200 p-8 text-center shadow-xs flex flex-col items-center justify-center space-y-2">
            <p className="text-sm font-bold text-slate-800">No hay laboratorios creados todavía</p>
            <p className="text-xs text-slate-500 max-w-md">
              {user?.role === 'teacher'
                ? 'Haz clic en "+ Nuevo Laboratorio" arriba para subir el documento (.pdf o .docx) de tu primer laboratorio y crear su rúbrica (100 %).'
                : 'Cuando el docente cree los laboratorios de Cohorte 1 y Cohorte 2, aparecerán aquí con sus objetivos y rúbricas.'}
            </p>
          </div>
        ) : (
          <div className="lg:col-span-8 space-y-5">
            {/* Lab Details */}
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
              <div className="flex items-center justify-between gap-2 mb-2">
                <span className="px-2.5 py-0.5 rounded bg-indigo-100 text-indigo-800 text-xs font-bold">
                  Cohorte {selectedLab.cohort_number} · {selectedLab.code}
                </span>
                {user?.role === 'teacher' && (
                  <button
                    type="button"
                    onClick={() => handleDeleteLab(selectedLab)}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-rose-200 bg-rose-50 hover:bg-rose-100 text-rose-700 text-xs font-semibold cursor-pointer"
                  >
                    <Trash2 className="w-3.5 h-3.5" /> Eliminar Laboratorio
                  </button>
                )}
              </div>
              <h2 className="text-lg font-bold text-slate-900">{selectedLab.title}</h2>
              <p className="text-sm text-slate-600 mt-2">{selectedLab.description}</p>
              {selectedLab.objectives?.length > 0 && (
                <div className="mt-4">
                  <h3 className="text-xs font-bold uppercase text-slate-500 mb-1.5">Objetivos de aprendizaje</h3>
                  <ul className="list-disc pl-5 text-xs text-slate-700 space-y-1">
                    {selectedLab.objectives.map((obj, i) => <li key={i}>{obj}</li>)}
                  </ul>
                </div>
              )}
              <div className="flex flex-wrap gap-1.5 mt-4">
                {(selectedLab.ai_topics || []).map((t, i) => (
                  <span key={i} className="text-[11px] px-2.5 py-1 rounded-full bg-slate-100 text-slate-700 font-medium">
                    #{t}
                  </span>
                ))}
              </div>
            </div>

            {/* AI Rubric Importer */}
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-indigo-600" />
                  Cargar e Interpretar Rúbrica (PDF o Texto)
                </h3>
                <label className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-xs font-semibold text-slate-700 cursor-pointer">
                  <FileUp className="w-3.5 h-3.5" />
                  Subir Rúbrica (PDF / DOCX)
                  <input type="file" accept=".pdf,.docx,.txt,.md" className="hidden" onChange={handleParsePdf} />
                </label>
              </div>
              <textarea
                rows={2}
                value={rawRubricText}
                onChange={(e) => setRawRubricText(e.target.value)}
                placeholder="O pega aquí criterios en texto plano, ej:&#10;Implementación del algoritmo - 40%&#10;Análisis de resultados - 35%&#10;Calidad de código y pruebas - 25%"
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs"
              />
              <button
                type="button"
                disabled={busy || !rawRubricText.trim()}
                onClick={handleParseText}
                className="px-3.5 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold disabled:opacity-50 cursor-pointer"
              >
                Interpretar y Parametrizar Rúbrica
              </button>
            </div>

            {/* Rubric Criteria Editor with 100% live check */}
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex-1">
                  <label className="block text-[11px] font-bold uppercase text-slate-500">Título de la Rúbrica</label>
                  <input
                    value={rubricTitle}
                    onChange={(e) => setRubricTitle(e.target.value)}
                    className="mt-1 w-full px-3 py-1.5 rounded-lg border border-slate-300 text-sm font-semibold"
                  />
                </div>
                <div
                  className={`px-3.5 py-2 rounded-xl border text-sm font-bold flex items-center gap-2 ${
                    isSum100
                      ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
                      : 'bg-rose-50 border-rose-200 text-rose-700'
                  }`}
                >
                  {isSum100 ? <CheckCircle2 className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
                  Suma: {totalWeight} %
                </div>
              </div>

              {msg.text && (
                <div
                  className={`p-3 rounded-lg text-xs font-medium border ${
                    msg.type === 'ok'
                      ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                      : 'bg-rose-50 border-rose-200 text-rose-800'
                  }`}
                >
                  {msg.text}
                </div>
              )}

              {validation && !validation.is_valid && (
                <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 space-y-1">
                  <p className="font-bold">Inconsistencias detectadas (corregir antes de evaluar):</p>
                  <ul className="list-disc pl-5">
                    {validation.errors.map((err, i) => <li key={i}>{err}</li>)}
                  </ul>
                </div>
              )}

              <div className="space-y-3">
                {criteria.map((crit, idx) => (
                  <div key={idx} className="p-4 rounded-xl border border-slate-200 bg-slate-50/70 space-y-2.5">
                    <div className="grid sm:grid-cols-12 gap-2.5 items-center">
                      <div className="sm:col-span-5">
                        <label className="text-[11px] font-semibold text-slate-500">Criterio ({crit.id})</label>
                        <input
                          value={crit.name}
                          onChange={(e) => updateCriterion(idx, 'name', e.target.value)}
                          className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white text-xs font-semibold"
                        />
                      </div>
                      <div className="sm:col-span-4">
                        <label className="text-[11px] font-semibold text-slate-500">Competencia</label>
                        <input
                          value={crit.competency}
                          onChange={(e) => updateCriterion(idx, 'competency', e.target.value)}
                          className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white text-xs"
                        />
                      </div>
                      <div className="sm:col-span-2">
                        <label className="text-[11px] font-semibold text-slate-500">Peso (%)</label>
                        <input
                          type="number"
                          step="1"
                          min="1"
                          max="100"
                          value={crit.weight_percent}
                          onChange={(e) => updateCriterion(idx, 'weight_percent', Number(e.target.value))}
                          className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white text-xs font-bold text-indigo-700"
                        />
                      </div>
                      <div className="sm:col-span-1 flex justify-end pt-4">
                        <button
                          type="button"
                          onClick={() => removeCriterion(idx)}
                          className="p-1.5 text-slate-400 hover:text-rose-600 cursor-pointer"
                          title="Eliminar criterio"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                    <div className="grid sm:grid-cols-2 gap-2">
                      {(crit.levels || []).map((lvl, lIdx) => (
                        <div key={lIdx} className="text-[11px] bg-white border border-slate-200 rounded-lg p-2">
                          <span className="font-bold text-slate-700">{lvl.label}</span>{' '}
                          <span className="text-slate-400">({Math.round(lvl.score_ratio * 100)}%)</span>
                          <p className="text-slate-600 mt-0.5">{lvl.descriptor}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 pt-2">
                <button
                  type="button"
                  onClick={addCriterion}
                  className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-slate-300 hover:bg-slate-100 text-xs font-semibold cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" /> Añadir Criterio
                </button>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={handleValidate}
                    className="px-3.5 py-2 rounded-lg border border-slate-300 hover:bg-slate-100 text-xs font-semibold cursor-pointer"
                  >
                    Validar Consistencia
                  </button>
                  <button
                    type="button"
                    disabled={busy || !isSum100}
                    onClick={handleSaveRubric}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold disabled:opacity-50 cursor-pointer"
                  >
                    <Save className="w-3.5 h-3.5" /> Guardar Nueva Versión (100 %)
                  </button>
                </div>
              </div>
            </div>

            {/* Version History */}
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
              <h3 className="text-xs font-bold uppercase text-slate-500 mb-3 flex items-center gap-1.5">
                <History className="w-4 h-4" /> Historial de Versiones Inmutables ({rubricVersions.length})
              </h3>
              <div className="space-y-2">
                {rubricVersions.map((rv) => (
                  <div key={rv.id} className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-xs">
                    <div>
                      <span className="font-bold text-slate-900">v{rv.version_number} — {rv.title}</span>
                      <span className="text-slate-500 ml-2">({rv.criteria.length} criterios · {rv.total_weight}%)</span>
                    </div>
                    {rv.is_active ? (
                      <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-semibold text-[11px]">
                        Activa
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded-full bg-slate-200 text-slate-600 font-semibold text-[11px]">
                        Histórica
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
