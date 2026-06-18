"use client";
import { useState, useEffect } from "react";

interface SellerDetail { seller_id: number; fullname: string; leads: number; gestionados: number; ventas: number; conversion: number; }
interface SupervisorRow { supervisor_id: number; supervisor_nombre: string; leads: number; gestionados: number; ventas: number; conversion: number; vendedores: number; _sellers: SellerDetail[]; }

export default function SupervisoresPage() {
  const [data, setData] = useState<SupervisorRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState<keyof SupervisorRow>("ventas");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [drilldown, setDrilldown] = useState<{ id: number; name: string; sellers: SellerDetail[] } | null>(null);
  const [filters, setFilters] = useState({ fecha_desde: "", fecha_hasta: "", fuente: "" });

  useEffect(() => {
    const token = localStorage.getItem("token"); if (!token) return;
    const params = new URLSearchParams();
    if (filters.fecha_desde) params.append("fecha_desde", filters.fecha_desde);
    if (filters.fecha_hasta) params.append("fecha_hasta", filters.fecha_hasta);
    if (filters.fuente) params.append("fuente", filters.fuente);
    fetch(`/api/dashboard/supervisores?${params}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(res => res.json()).then(d => { setData(d || []); setLoading(false); }).catch(() => setLoading(false));
  }, [filters]);

  const sorted = [...data].sort((a, b) => {
    const av = a[sortBy] ?? 0; const bv = b[sortBy] ?? 0;
    return sortDir === "desc" ? Number(bv) - Number(av) : Number(av) - Number(bv);
  });
  const handleSort = (col: keyof SupervisorRow) => {
    if (sortBy === col) setSortDir(sortDir === "desc" ? "asc" : "desc");
    else { setSortBy(col); setSortDir("desc"); }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-[590] text-porcelain tracking-[-0.22px]">Supervisores</h1>
      <p className="text-storm-cloud text-sm -mt-4">Métricas por supervisor — click en uno para ver los vendedores de su equipo</p>

      <div className="flex flex-wrap gap-3 items-end">
        <div><label className="block text-storm-cloud text-xs mb-1">Desde</label><input type="date" value={filters.fecha_desde} onChange={e => setFilters({ ...filters, fecha_desde: e.target.value })} className="bg-pitch-black border border-charcoal-grey rounded-md px-3 py-2 text-porcelain text-sm focus:border-neon-lime focus:outline-none" /></div>
        <div><label className="block text-storm-cloud text-xs mb-1">Hasta</label><input type="date" value={filters.fecha_hasta} onChange={e => setFilters({ ...filters, fecha_hasta: e.target.value })} className="bg-pitch-black border border-charcoal-grey rounded-md px-3 py-2 text-porcelain text-sm focus:border-neon-lime focus:outline-none" /></div>
        <div><label className="block text-storm-cloud text-xs mb-1">Fuente</label><select value={filters.fuente} onChange={e => setFilters({ ...filters, fuente: e.target.value })} className="bg-pitch-black border border-charcoal-grey rounded-md px-3 py-2 text-porcelain text-sm focus:border-neon-lime focus:outline-none"><option value="">Todas</option><option value="Botmaker">Botmaker</option><option value="ThinkChat">ThinkChat</option><option value="Manual">Manual</option></select></div>
      </div>

      <div className="bg-graphite rounded-md shadow-[rgba(0,0,0,0.4)_0px_2px_4px_0px] overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-charcoal-grey text-storm-cloud text-xs font-[510]">
            {([{ key: "supervisor_nombre", label: "Supervisor" }, { key: "vendedores", label: "Equipo" }, { key: "leads", label: "Leads" }, { key: "gestionados", label: "Gestionados" }, { key: "ventas", label: "Ventas" }, { key: "conversion", label: "% Conv." }] as { key: keyof SupervisorRow; label: string }[]).map(col => (
              <th key={col.key} onClick={() => handleSort(col.key)} className="px-4 py-3 text-left cursor-pointer hover:text-light-steel transition-colors select-none">
                {col.label}{sortBy === col.key && <span className="ml-1 text-porcelain">{sortDir === "desc" ? "v" : "^"}</span>}
              </th>
            ))}
          </tr></thead>
          <tbody>
            {loading ? [...Array(5)].map((_, i) => (<tr key={i} className="border-b border-charcoal-grey">{[...Array(6)].map((_, j) => (<td key={j} className="px-4 py-3"><div className="h-4 bg-charcoal-grey rounded animate-pulse" /></td>))}</tr>))
            : sorted.map(row => (
              <tr key={row.supervisor_id} onClick={() => setDrilldown({ id: row.supervisor_id, name: row.supervisor_nombre, sellers: row._sellers || [] })} className="border-b border-charcoal-grey/50 hover:bg-deep-slate/50 transition-colors cursor-pointer">
                <td className="px-4 py-3 text-aether-blue font-[510]">{row.supervisor_nombre}</td>
                <td className="px-4 py-3 text-light-steel">{row.vendedores}</td>
                <td className="px-4 py-3 text-light-steel">{row.leads.toLocaleString()}</td>
                <td className="px-4 py-3 text-light-steel">{row.gestionados.toLocaleString()}</td>
                <td className="px-4 py-3 text-porcelain font-[590]">{row.ventas.toLocaleString()}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1.5 bg-pitch-black rounded-full overflow-hidden min-w-[60px]">
                      <div className="h-full rounded-full" style={{ width: `${Math.min(100, row.conversion * 2)}%`, background: row.conversion >= 10 ? "linear-gradient(90deg, #008d2c, #27a644)" : row.conversion >= 5 ? "linear-gradient(90deg, #e4f222, #f59e0b)" : "linear-gradient(90deg, #5e6ad2, #8b5cf6)" }} />
                    </div>
                    <span className={`text-xs w-10 text-right ${row.conversion >= 10 ? "text-emerald" : row.conversion >= 5 ? "text-amber-300" : "text-storm-cloud"}`}>{row.conversion}%</span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Drilldown panel */}
      {drilldown && (
        <div className="bg-graphite rounded-md p-6 shadow-[rgba(0,0,0,0.4)_0px_2px_4px_0px] border-l-2 border-neon-lime">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-[590] text-porcelain">Vendedores — {drilldown.name}</h2>
            <button onClick={() => setDrilldown(null)} className="text-storm-cloud hover:text-porcelain text-sm">Cerrar</button>
          </div>
          <table className="w-full text-sm">
            <thead><tr className="border-b border-charcoal-grey text-storm-cloud text-xs font-[510]"><th className="px-4 py-2 text-left">#</th><th className="px-4 py-2 text-left">Vendedor</th><th className="px-4 py-2 text-left">Leads</th><th className="px-4 py-2 text-left">Gestionados</th><th className="px-4 py-2 text-left">Ventas</th><th className="px-4 py-2 text-left">% Conv.</th></tr></thead>
            <tbody>
              {drilldown.sellers.map(s => (
                <tr key={s.seller_id} className="border-b border-charcoal-grey/30">
                  <td className="px-4 py-2 text-fog-grey">{s.seller_id}</td>
                  <td className="px-4 py-2 text-porcelain font-[510]">{s.fullname}</td>
                  <td className="px-4 py-2 text-light-steel">{s.leads.toLocaleString()}</td>
                  <td className="px-4 py-2 text-light-steel">{s.gestionados.toLocaleString()}</td>
                  <td className="px-4 py-2 text-porcelain font-[590]">{s.ventas.toLocaleString()}</td>
                  <td className="px-4 py-2"><span className={s.conversion >= 10 ? "text-emerald" : "text-storm-cloud"}>{s.conversion.toFixed(1)}%</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
