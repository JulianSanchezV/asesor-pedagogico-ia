import React, { useEffect, useState } from 'react';
import { CheckCircle2, Cpu, KeyRound, Save, ShieldAlert } from 'lucide-react';
import { apiFetch } from '../api/client';
import { useAuth } from '../context/AuthContext';

export default function SettingsPage() {
  const { user } = useAuth();
  const [cfg, setCfg] = useState(null);
  const [provider, setProvider] = useState('gemini');
  const [modelName, setModelName] = useState('gemini-3.5-flash-lite');
  const [baseUrl, setBaseUrl] = useState('');
  const [apiKeyOverride, setApiKeyOverride] = useState('');
  const [msg, setMsg] = useState({ type: '', text: '' });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    apiFetch('/api/settings/ai').then((data) => {
      setCfg(data);
      setProvider(data.provider);
      setModelName(data.model_name);
      setBaseUrl(data.base_url || '');
    });
  }, []);

  const handleSelectProvider = (provId) => {
    setProvider(provId);
    const meta = cfg?.available_providers?.find((p) => p.id === provId);
    if (meta) {
      setModelName(meta.default_model);
      setBaseUrl(meta.default_base_url || '');
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setMsg({ type: '', text: '' });
    try {
      const updated = await apiFetch('/api/settings/ai', {
        method: 'PUT',
        body: JSON.stringify({
          provider,
          model_name: modelName,
          base_url: baseUrl,
          api_key_override: apiKeyOverride,
        }),
      });
      setCfg(updated);
      setApiKeyOverride('');
      setMsg({ type: 'ok', text: `Proveedor IA actualizado a ${updated.provider} (${updated.model_name}).` });
    } catch (err) {
      setMsg({ type: 'err', text: err.message });
    } finally {
      setSaving(false);
    }
  };

  if (!cfg) return <div className="p-8 text-sm text-slate-500">Cargando configuración de modelos IA...</div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Configuración de Modelos de IA (Nube / Local)</h1>
        <p className="text-sm text-slate-500">
          Arquitectura desacoplada compatible con Google Gemini (multimodal), Groq, OpenRouter y Ollama local.
        </p>
      </div>

      <div className="grid lg:grid-cols-12 gap-6">
        <form onSubmit={handleSave} className="lg:col-span-6 bg-white rounded-xl border border-slate-200 p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-bold text-slate-900 text-sm flex items-center gap-2">
              <Cpu className="w-4 h-4 text-indigo-600" />
              Proveedor Activo
            </h2>
            <span
              className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
                cfg.has_api_key ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
              }`}
            >
              {cfg.has_api_key ? 'Conexión lista' : 'Sin API Key (modo local heurístico)'}
            </span>
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

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Proveedor de IA</label>
            <select
              value={provider}
              disabled={user?.role !== 'teacher'}
              onChange={(e) => handleSelectProvider(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white disabled:bg-slate-100"
            >
              {cfg.available_providers.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Nombre del Modelo</label>
            <input
              value={modelName}
              disabled={user?.role !== 'teacher'}
              onChange={(e) => setModelName(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm disabled:bg-slate-100"
            />
          </div>

          {provider !== 'gemini' && (
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Base URL (OpenAI-compatible / Ollama)</label>
              <input
                value={baseUrl}
                disabled={user?.role !== 'teacher'}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="http://localhost:11434/v1"
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm disabled:bg-slate-100"
              />
            </div>
          )}

          {user?.role === 'teacher' ? (
            <>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1 flex items-center gap-1">
                  <KeyRound className="w-3.5 h-3.5 text-slate-400" />
                  API Key (opcional si ya la pusiste en el archivo .env del backend)
                </label>
                <input
                  type="password"
                  value={apiKeyOverride}
                  onChange={(e) => setApiKeyOverride(e.target.value)}
                  placeholder="Pega aquí tu GEMINI_API_KEY gratuita de Google AI Studio"
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
                />
              </div>

              <button
                type="submit"
                disabled={saving}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold cursor-pointer disabled:opacity-60"
              >
                <Save className="w-4 h-4" />
                {saving ? 'Guardando...' : 'Guardar Configuración'}
              </button>
            </>
          ) : (
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-600 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-slate-400 shrink-0" />
              Solo usuarios con rol Docente pueden modificar el proveedor de IA y las claves API.
            </div>
          )}
        </form>

        {/* Documentation of Providers, Costs & Limitations (Engineering Condition #4) */}
        <div className="lg:col-span-6 space-y-3">
          <h2 className="font-bold text-slate-900 text-sm">
            Comparativa de Modelos, Requisitos, Costos y Limitaciones
          </h2>
          {cfg.available_providers.map((p) => (
            <div
              key={p.id}
              className={`bg-white rounded-xl border p-4 shadow-xs space-y-1.5 ${
                p.id === provider ? 'border-indigo-500 ring-1 ring-indigo-200' : 'border-slate-200'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-bold text-sm text-slate-900">{p.name}</span>
                {p.multimodal && (
                  <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-800">
                    Multimodal (PDF + Imágenes)
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-600">
                <CheckCircle2 className="w-3.5 h-3.5 inline text-emerald-600 mr-1" />
                <strong>Costos:</strong> {p.cost_info}
              </p>
              <p className="text-xs text-slate-500">
                <strong>Limitaciones:</strong> {p.limitations}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
