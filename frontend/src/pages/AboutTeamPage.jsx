import React, { useEffect, useState } from 'react';
import { BrainCircuit, Code2, Sparkles, Users } from 'lucide-react';
import { apiFetch } from '../api/client';
import teamMembers from '../data/team.json';

export default function AboutTeamPage() {
  const [info, setInfo] = useState(null);

  useEffect(() => {
    apiFetch('/api/settings/project-info').then(setInfo).catch(() => null);
  }, []);

  return (
    <div className="space-y-8">
      {/* Project Abstract Hero */}
      <div className="bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 text-white rounded-2xl p-8 shadow-lg">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-12 h-12 rounded-xl bg-indigo-600 flex items-center justify-center">
            <BrainCircuit className="w-7 h-7 text-white" />
          </div>
          <div>
            <p className="text-xs uppercase tracking-wider text-indigo-300 font-bold">
              {info?.institution || 'Universidad de Manizales — Facultad de Ciencias e Ingeniería'}
            </p>
            <h1 className="text-2xl font-bold">{info?.project_name || 'Asesor Pedagógico Inteligente'}</h1>
          </div>
        </div>
        <p className="text-xs text-indigo-200 font-medium mb-4">
          {info?.program || 'Ingeniería de Sistemas y Telecomunicaciones · Profundización I - Inteligencia Artificial'}
        </p>
        <div className="bg-white/10 border border-white/15 rounded-xl p-5 backdrop-blur-xs">
          <h2 className="text-xs font-bold uppercase tracking-wider text-indigo-300 mb-2">Abstract del Proyecto</h2>
          <p className="text-sm text-slate-100 leading-relaxed">
            {info?.abstract ||
              'Plataforma web inteligente para la evaluación verificable, retroalimentación argumentada y fortalecimiento de competencias en Inteligencia Artificial.'}
          </p>
        </div>
      </div>

      {/* Team Section (Mandatory Feature #7) */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <Users className="w-5 h-5 text-indigo-600" />
            Equipo Desarrollador
          </h2>
          <span className="text-xs font-medium text-slate-500">Ingeniería de Sistemas · Octavo Semestre</span>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {teamMembers.map((member, i) => (
            <div key={i} className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs flex flex-col items-center text-center">
              <img
                src={member.avatar}
                alt={member.name}
                className="w-24 h-24 rounded-full object-cover border-4 border-indigo-100 shadow-sm mb-4"
              />
              <h3 className="font-bold text-base text-slate-900">{member.name}</h3>
              <span className="mt-1 px-3 py-0.5 rounded-full bg-indigo-50 text-indigo-700 text-xs font-semibold">
                {member.role}
              </span>
              <p className="text-xs text-slate-600 mt-3 leading-relaxed">{member.bio}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Architecture & Tech Stack */}
      {info?.technologies && (
        <section className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-4">
          <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <Code2 className="w-5 h-5 text-indigo-600" />
            Tecnologías y Arquitectura Implementada
          </h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {info.technologies.map((t, i) => (
              <div key={i} className="p-4 rounded-xl bg-slate-50 border border-slate-200">
                <p className="text-xs font-bold uppercase text-indigo-700">{t.layer}</p>
                <p className="text-sm font-semibold text-slate-900 mt-1">{t.stack}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* AI-Augmented Engineering Log (Engineering Condition #1) */}
      {info?.ai_engineering_log && (
        <section className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-4">
          <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-amber-500" />
            Bitácora de Ingeniería de Software Aumentada por IA
          </h2>
          <div className="space-y-3">
            {info.ai_engineering_log.map((item, i) => (
              <div key={i} className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-1.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-bold text-sm text-slate-900">{item.phase}</span>
                  <span className="text-xs px-2.5 py-0.5 rounded-full bg-indigo-100 text-indigo-800 font-semibold">
                    {item.tools}
                  </span>
                </div>
                <p className="text-xs text-slate-700"><strong>Aporte de la IA:</strong> {item.contribution}</p>
                <p className="text-xs text-slate-600"><strong>Decisión técnica del equipo:</strong> {item.human_decision}</p>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
