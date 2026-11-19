import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BrainCircuit, ShieldCheck, Sparkles, UserCheck, AlertCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function LoginPage() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState('login'); // login | register
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('estudiante@umanizales.edu.co');
  const [password, setPassword] = useState('Estudiante123!');
  const [role, setRole] = useState('student');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      if (mode === 'login') {
        await login(email, password);
      } else {
        await register(fullName, email, password, role);
      }
      navigate('/');
    } catch (err) {
      setError(err.message || 'No se pudo iniciar sesión.');
    } finally {
      setBusy(false);
    }
  };

  const fillDemo = (type) => {
    setMode('login');
    setError('');
    if (type === 'teacher') {
      setEmail('docente@umanizales.edu.co');
      setPassword('Docente123!');
    } else {
      setEmail('estudiante@umanizales.edu.co');
      setPassword('Estudiante123!');
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-indigo-950 to-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-5xl grid md:grid-cols-2 bg-white rounded-2xl shadow-2xl overflow-hidden">
        {/* Left Hero */}
        <div className="bg-slate-900 text-white p-8 md:p-10 flex flex-col justify-between relative overflow-hidden">
          <div className="relative z-10">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/20 border border-indigo-400/30 text-indigo-200 text-xs font-medium mb-6">
              <Sparkles className="w-3.5 h-3.5" />
              Universidad de Manizales · Profundización I IA
            </div>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-xl bg-indigo-600 flex items-center justify-center shadow-lg">
                <BrainCircuit className="w-7 h-7 text-white" />
              </div>
              <h1 className="text-2xl font-bold tracking-tight">Asesor Pedagógico Inteligente</h1>
            </div>
            <p className="text-slate-300 text-sm leading-relaxed mb-8">
              Plataforma web inteligente para la autoevaluación, verificación técnica en sandbox, retroalimentación
              explicable y mapa mental interactivo de competencias en Inteligencia Artificial (Cohortes 1 y 2).
            </p>
            <div className="space-y-3 text-xs text-slate-300">
              <div className="flex items-start gap-2.5">
                <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                <span>Salidas estructuradas Pydantic y nota 0.0–5.0 calculada deterministamente en backend.</span>
              </div>
              <div className="flex items-start gap-2.5">
                <UserCheck className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
                <span>Trazabilidad completa, versionamiento de rúbricas (100 %) y aprobación docente.</span>
              </div>
            </div>
          </div>

          <div className="mt-8 pt-6 border-t border-slate-800 relative z-10">
            <p className="text-xs text-slate-400 mb-2.5 font-medium">Acceso rápido cuentas de demostración:</p>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => fillDemo('student')}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-indigo-600 text-xs font-medium transition cursor-pointer"
              >
                Usar cuenta Estudiante
              </button>
              <button
                type="button"
                onClick={() => fillDemo('teacher')}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-emerald-600 text-xs font-medium transition cursor-pointer"
              >
                Usar cuenta Docente
              </button>
            </div>
          </div>
        </div>

        {/* Right Form */}
        <div className="p-8 md:p-10 flex flex-col justify-center">
          <div className="flex gap-2 p-1 bg-slate-100 rounded-xl mb-6">
            <button
              type="button"
              onClick={() => { setMode('login'); setError(''); }}
              className={`flex-1 py-2 text-sm font-semibold rounded-lg transition cursor-pointer ${
                mode === 'login' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500'
              }`}
            >
              Iniciar Sesión
            </button>
            <button
              type="button"
              onClick={() => { setMode('register'); setError(''); }}
              className={`flex-1 py-2 text-sm font-semibold rounded-lg transition cursor-pointer ${
                mode === 'register' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500'
              }`}
            >
              Crear Cuenta
            </button>
          </div>

          {error && (
            <div className="mb-4 p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'register' && (
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Nombre completo</label>
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Ej. María Fernanda Torres"
                  className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Correo electrónico</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="correo@umanizales.edu.co"
                className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Contraseña</label>
              <input
                type="password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            {mode === 'register' && (
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Perfil en la plataforma</label>
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="student">Estudiante (Portafolio, Autoevaluación y Mapa Mental)</option>
                  <option value="teacher">Docente (Gestión de Rúbricas y Aprobación)</option>
                </select>
              </div>
            )}

            <button
              type="submit"
              disabled={busy}
              className="w-full py-2.5 px-4 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm transition shadow-sm disabled:opacity-60 cursor-pointer"
            >
              {busy ? 'Procesando...' : mode === 'login' ? 'Ingresar a la Plataforma' : 'Registrarse'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
