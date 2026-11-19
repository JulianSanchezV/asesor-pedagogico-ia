import React, { useEffect, useRef, useState } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
} from '@xyflow/react';
import { toPng, toSvg } from 'html-to-image';
import { Download, Info, Layers, Sparkles, Compass } from 'lucide-react';
import { apiFetch } from '../api/client';
import { useAuth } from '../context/AuthContext';
import StatusBadge from '../components/StatusBadge';

const MASTERY_STYLES = {
  avanzado: { bg: '#dcfce7', border: '#16a34a', text: '#14532d' },
  intermedio: { bg: '#dbeafe', border: '#2563eb', text: '#1e3a8a' },
  basico: { bg: '#fef3c7', border: '#d97706', text: '#78350f' },
  por_fortalecer: { bg: '#ffe4e6', border: '#e11d48', text: '#881337' },
  pendiente: { bg: '#f1f5f9', border: '#94a3b8', text: '#334155' },
};

export default function MindMapPage() {
  const { user } = useAuth();
  const canvasRef = useRef(null);
  const [students, setStudents] = useState([]);
  const [selectedStudentId, setSelectedStudentId] = useState('');
  const [rawMap, setRawMap] = useState(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNode, setSelectedNode] = useState(null);
  const [loading, setLoading] = useState(true);

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
    apiFetch(`/api/reports/mindmap${query}`)
      .then((data) => {
        setRawMap(data);
        const rfNodes = data.nodes.map((n) => {
          const palette = MASTERY_STYLES[n.mastery_level] || MASTERY_STYLES.pendiente;
          const isRoot = n.type === 'root';
          const isCategory = n.type === 'category';
          return {
            id: n.id,
            position: n.position,
            data: {
              label: (
                <div className="text-center px-1">
                  <div className="font-bold text-xs leading-snug whitespace-pre-line">{n.label}</div>
                  {n.mastery_score > 0 && (
                    <div className="text-[10px] font-semibold opacity-80 mt-0.5">
                      Dominio: {n.mastery_score}/5.0
                    </div>
                  )}
                </div>
              ),
              meta: n,
            },
            style: {
              background: isRoot ? '#1e1b4b' : isCategory ? '#0f172a' : palette.bg,
              color: isRoot || isCategory ? '#ffffff' : palette.text,
              border: `2px solid ${isRoot ? '#6366f1' : isCategory ? '#334155' : palette.border}`,
              borderRadius: isRoot ? 16 : 12,
              padding: isRoot ? '12px 16px' : '8px 12px',
              width: isRoot ? 220 : isCategory ? 190 : 185,
              boxShadow: '0 4px 10px rgba(15, 23, 42, 0.08)',
              cursor: 'pointer',
            },
          };
        });

        const rfEdges = data.edges.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          label: e.relation_type === 'conceptual' ? e.label : undefined,
          animated: e.relation_type === 'conceptual',
          style: {
            stroke: e.relation_type === 'conceptual' ? '#6366f1' : '#94a3b8',
            strokeWidth: e.relation_type === 'conceptual' ? 2 : 1.5,
            strokeDasharray: e.relation_type === 'conceptual' ? '5 4' : undefined,
          },
          labelStyle: { fontSize: 10, fill: '#4338ca', fontWeight: 600 },
          markerEnd: { type: MarkerType.ArrowClosed, color: e.relation_type === 'conceptual' ? '#6366f1' : '#94a3b8' },
        }));

        setNodes(rfNodes);
        setEdges(rfEdges);
        setSelectedNode(data.nodes[0] || null);
      })
      .finally(() => setLoading(false));
  }, [selectedStudentId, user?.role]);

  const exportImage = async (format) => {
    if (!canvasRef.current) return;
    const fn = format === 'svg' ? toSvg : toPng;
    const dataUrl = await fn(canvasRef.current, { backgroundColor: '#f8fafc' });
    const a = document.createElement('a');
    a.href = dataUrl;
    a.download = `mapa_mental_ia.${format}`;
    a.click();
  };

  const exportJson = () => {
    if (!rawMap) return;
    const blob = new Blob([JSON.stringify(rawMap, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'mapa_mental_ia.json';
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) return <div className="p-8 text-sm text-slate-500">Generando mapa mental interactivo de competencias...</div>;

  return (
    <div className="space-y-5">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Mapa Mental Interactivo de Competencias en IA</h1>
          <p className="text-sm text-slate-500">
            Navega, haz zoom y selecciona cualquier temática para inspeccionar laboratorios, evidencias, dominio y áreas de profundización.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
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
            onClick={() => exportImage('png')}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" /> PNG
          </button>
          <button
            onClick={() => exportImage('svg')}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-900 text-white text-xs font-semibold cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" /> SVG
          </button>
          <button
            onClick={exportJson}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-slate-300 hover:bg-slate-100 text-slate-700 text-xs font-semibold cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" /> JSON
          </button>
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-3 text-xs bg-white px-4 py-2.5 rounded-xl border border-slate-200">
        <span className="font-bold text-slate-700">Niveles de dominio:</span>
        <span className="inline-flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-emerald-500" /> Avanzado (≥ 4.3)</span>
        <span className="inline-flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-blue-500" /> Intermedio (3.5–4.2)</span>
        <span className="inline-flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-amber-500" /> Básico (2.8–3.4)</span>
        <span className="inline-flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-rose-500" /> Por fortalecer (&lt; 2.8)</span>
        <span className="inline-flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-slate-400" /> Pendiente</span>
      </div>

      <div className="grid lg:grid-cols-12 gap-5">
        {/* Interactive React Flow Canvas */}
        <div
          ref={canvasRef}
          className="lg:col-span-8 h-[560px] bg-slate-50 rounded-2xl border border-slate-200 overflow-hidden shadow-xs"
        >
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={(_, node) => setSelectedNode(node.data.meta)}
            fitView
            fitViewOptions={{ padding: 0.2 }}
          >
            <Background color="#cbd5e1" gap={18} />
            <Controls />
            <MiniMap zoomable pannable />
          </ReactFlow>
        </div>

        {/* Node Detail Inspector */}
        <div className="lg:col-span-4 bg-white rounded-2xl border border-slate-200 p-5 shadow-xs flex flex-col justify-between space-y-4">
          {selectedNode ? (
            <div className="space-y-4">
              <div>
                <p className="text-[11px] uppercase font-bold text-indigo-600">{selectedNode.category}</p>
                <h2 className="text-lg font-bold text-slate-900 mt-0.5 whitespace-pre-line">{selectedNode.label}</h2>
                <div className="flex items-center gap-2.5 mt-2">
                  <StatusBadge value={selectedNode.mastery_level} />
                  {selectedNode.mastery_score > 0 && (
                    <span className="text-sm font-extrabold text-slate-900">{selectedNode.mastery_score} / 5.0</span>
                  )}
                </div>
              </div>

              <div>
                <h3 className="text-xs font-bold uppercase text-slate-500 mb-1.5 flex items-center gap-1.5">
                  <Layers className="w-3.5 h-3.5 text-indigo-600" /> Laboratorios donde se aplicó
                </h3>
                <ul className="space-y-1 text-xs text-slate-700">
                  {(selectedNode.labs_applied || []).map((lb, i) => (
                    <li key={i} className="px-2.5 py-1.5 rounded-lg bg-slate-50 border border-slate-200 font-medium">
                      {lb}
                    </li>
                  ))}
                </ul>
              </div>

              <div>
                <h3 className="text-xs font-bold uppercase text-slate-500 mb-1.5 flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-emerald-600" /> Evidencias de aprendizaje
                </h3>
                <ul className="list-disc pl-4 text-xs text-slate-700 space-y-1">
                  {(selectedNode.evidences || []).map((ev, i) => <li key={i}>{ev}</li>)}
                </ul>
              </div>

              <div>
                <h3 className="text-xs font-bold uppercase text-slate-500 mb-1.5 flex items-center gap-1.5">
                  <Compass className="w-3.5 h-3.5 text-amber-600" /> Aspectos que requieren profundización
                </h3>
                <ul className="list-disc pl-4 text-xs text-amber-900 space-y-1 bg-amber-50/70 border border-amber-200 rounded-lg p-3 pl-6">
                  {(selectedNode.needs_deepening?.length ? selectedNode.needs_deepening : ['Sin brechas críticas identificadas.']).map((nd, i) => (
                    <li key={i}>{nd}</li>
                  ))}
                </ul>
              </div>
            </div>
          ) : (
            <div className="text-sm text-slate-500 flex items-center gap-2">
              <Info className="w-4 h-4" /> Haz clic en cualquier nodo del mapa mental para ver su detalle.
            </div>
          )}

          <p className="text-[11px] text-slate-400 border-t border-slate-100 pt-3">
            Tip: puedes arrastrar los nodos para reorganizar el mapa antes de descargarlo como PNG o SVG.
          </p>
        </div>
      </div>
    </div>
  );
}
