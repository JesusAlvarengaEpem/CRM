"use client";

import { useState, useEffect } from "react";

interface Etapa { nombre: string; valor: number; pct: number; }

export default function FunnelPage() {
  const [data, setData] = useState<Etapa[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ fecha_desde: "", fecha_hasta: "", enterprise_id: "", fuente: "" });

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) return;
    const params = new URLSearchParams();
    if (filters.fecha_desde) params.append("fecha_desde", filters.fecha_desde);
    if (filters.fecha_hasta) params.append("fecha_hasta", filters.fecha_hasta);
    if (filters.enterprise_id) params.append("enterprise_id", filters.enterprise_id);
    if (filters.fuente) params.append("fuente", filters.fuente);
    fetch("http://localhost:8000/api/dashboard/funnel?" + params, {
      headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
    }).then((res) => res.json()).then((d) => { setData(d.etapas || []); setLoading(false); }).catch(() => setLoading(false));
  }, [filters]);

  const maxVal = Math.max(...data.map((e) => e.valor), 1);
  const total = data[0]?.valor || 1;
  const colors = [
    "linear-gradient(90deg, #8a8f98, #d0d6e0)",
    "linear-gradient(90deg, #5e6ad2, #02b8cc)",
    "linear-gradient(90deg, #6366f1, #8b5cf6)",
    "linear-gradient(90deg, #f59e0b, #e4f222)",
    "linear-gradient(90deg, #27a644, #e4f222)",
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-[590] text-porcelain tracking-[-0.22px]">Funnel de Conversion</h1>
        <p className="text-storm-cloud text-sm mt-1">Cada lead aparece en una sola etapa — la mas avanzada</p>
      </div>

      <div className="flex flex-wrap gap-3 items-end">
        <div><label className="block text-storm-cloud text-xs mb-1">Desde</label><input type="date" value={filters.fecha_desde} onChange={(e) => setFilters({ ...filters, fecha_desde: e.target.value })} className="bg-pitch-black border border-charcoal-grey rounded-md px-3 py-2 text-porcelain text-sm focus:border-neon-lime focus:outline-none" /></div>
        <div><label className="block text-storm-cloud text-xs mb-1">Hasta</label><input type="date" value={filters.fecha_hasta} onChange={(e) => setFilters({ ...filters, fecha_hasta: e.target.value })} className="bg-pitch-black border border-charcoal-grey rounded-md px-3 py-2 text-porcelain text-sm focus:border-neon-lime focus:outline-none" /></div>
        <div><label className="block text-storm-cloud text-xs mb-1">UN</label><select value={filters.enterprise_id} onChange={(e) => setFilters({ ...filters, enterprise_id: e.target.value })} className="bg-pitch-black border border-charcoal-grey rounded-md px-3 py-2 text-porcelain text-sm focus:border-neon-lime focus:outline-none"><option value="">Todas</option><option value="1">Odontologia</option><option value="2">Med. Prepaga</option><option value="4">Emergencias</option><option value="5">Med. Estetica</option></select></div>
        <div><label className="block text-storm-cloud text-xs mb-1">Fuente</label><select value={filters.fuente} onChange={(e) => setFilters({ ...filters, fuente: e.target.value })} className="bg-pitch-black border border-charcoal-grey rounded-md px-3 py-2 text-porcelain text-sm focus:border-neon-lime focus:outline-none"><option value="">Todas</option><option value="Botmaker">Botmaker</option><option value="ThinkChat">ThinkChat</option><option value="Manual">Manual</option></select></div>
      </div>

      {loading ? (
        <div className="space-y-3">{[...Array(5)].map((_, i) => <div key={i} className="h-16 bg-graphite rounded animate-pulse" />)}</div>
      ) : (
        <div className="max-w-2xl">
          {/* Funnel bars */}
          <div className="space-y-0">
            {data.map((etapa, i) => {
              const drop = i > 0 ? data[i - 1].valor - etapa.valor : 0;
              const dropPct = i > 0 && data[i - 1].valor > 0 ? (drop / data[i - 1].valor * 100).toFixed(1) : null;
              return (
                <div key={i} className="flex items-center gap-4 p-3 group">
                  <div className="w-32 text-right shrink-0">
                    <p className="text-porcelain font-[510] text-sm">{etapa.nombre}</p>
                    {dropPct && <p className="text-warning-red text-[11px]">-{dropPct}% drop</p>}
                  </div>
                  <div className="flex-1">
                    <div className="h-8 bg-pitch-black rounded-r-full overflow-hidden">
                      <div
                        className="h-full rounded-r-full transition-all duration-700"
                        style={{ width: `${(etapa.valor / maxVal) * 100}%`, background: colors[i] }}
                      />
                    </div>
                  </div>
                  <div className="w-28 shrink-0 text-right">
                    <span className="text-porcelain font-[590] text-sm">{etapa.valor.toLocaleString()}</span>
                    <span className="text-storm-cloud text-xs ml-1">({etapa.pct}%)</span>
                  </div>
                </div>
              );
            })}
          </div>
          <p className="text-storm-cloud text-xs mt-2 text-right">Total: {total.toLocaleString()} leads</p>
        </div>
      )}
    </div>
  );
}

