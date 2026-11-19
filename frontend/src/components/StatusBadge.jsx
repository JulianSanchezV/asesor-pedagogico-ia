import React from 'react';

const STATUS_MAP = {
  approved: { label: 'Aprobada por Docente', cls: 'bg-emerald-100 text-emerald-800 border-emerald-200' },
  pending_review: { label: 'Preliminar (Pendiente Revisión)', cls: 'bg-amber-100 text-amber-800 border-amber-200' },
  uploaded: { label: 'Entregado (Sin evaluar)', cls: 'bg-slate-100 text-slate-700 border-slate-200' },
  avanzado: { label: 'Avanzado', cls: 'bg-emerald-100 text-emerald-800 border-emerald-200' },
  intermedio: { label: 'Intermedio', cls: 'bg-blue-100 text-blue-800 border-blue-200' },
  basico: { label: 'Básico', cls: 'bg-amber-100 text-amber-800 border-amber-200' },
  por_fortalecer: { label: 'Por Fortalecer', cls: 'bg-rose-100 text-rose-800 border-rose-200' },
  pendiente: { label: 'Pendiente', cls: 'bg-slate-100 text-slate-600 border-slate-200' },
  excelente: { label: 'Excelente', cls: 'bg-emerald-100 text-emerald-800 border-emerald-200' },
  sobresaliente: { label: 'Sobresaliente', cls: 'bg-blue-100 text-blue-800 border-blue-200' },
  aceptable: { label: 'Aceptable', cls: 'bg-amber-100 text-amber-800 border-amber-200' },
  insuficiente: { label: 'Insuficiente', cls: 'bg-rose-100 text-rose-800 border-rose-200' },
};

export default function StatusBadge({ value }) {
  const meta = STATUS_MAP[value] || { label: value || 'N/A', cls: 'bg-slate-100 text-slate-700 border-slate-200' };
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${meta.cls}`}>
      {meta.label}
    </span>
  );
}
