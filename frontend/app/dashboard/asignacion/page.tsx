"use client";
import { useState, useEffect } from "react";

interface GlobalData { total_leads: number; asignados: number; asignados_pct: number; sistema_epem: number; sistema_epem_pct: number; sin_seller: number; sin_seller_pct: number; huerfanos_total: number; huerfanos_pct: number; gestionados: number; ventas: number; }
interface UNRow { enterprise_id: number; un_nombre: string; total_leads: number; asignados: number; asignados_pct: number; huerfanos: number; huerfanos_pct: number; gestionados: number; ventas: number; }
interface FuenteRow { fuente: string; total_leads: number; asignados: number; asignados_pct: number; huerfanos: number; huerfanos_pct: number; gestionados: number; ventas: number; }
interface SupervisorRow { supervisor_id: number; supervisor_nombre: string; leads_asignados: number; gestionados: number; ventas: number; vendedores: number; tasa_gestion: number; }
interface TrendRow { mes_str: string; total_leads: number; asignados: number; asignados_pct: number; huerfanos: number; huerfanos_pct: number; }

interface FunnelData {
  global: GlobalData;
  por_un: UNRow[];
  por_fuente: FuenteRow[];
  por_supervisor: SupervisorRow[];
  trend_mensual: TrendRow[];
}

export default function AsignacionPage() {
  const [data, setData] = useState<FunnelData | null>(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ fecha_desde: "", fecha_hasta: "", fuente: "" });

  useEffect(() => {
    const t = localStorage.getItem("token"); if (!t) return;
    const params = new URLSearchParams();
    if (filters.fecha_desde) params.append("fecha_desde", filters.fecha_desde);
    if (filters.fecha_hasta) params.append("fecha_hasta", filters.fecha_hasta);
    if (filters.fuente) params.append("fuente", filters.fuente);
    fetch(`/api/dashboard/funnel-asignacion?${params}`, { headers: { Authorization: `Bearer ${t}` } })
      .then(r => r.json()).then(d => { setData(d); setLoading(false); }).catch(() => setLoading(false));
  }, [filters]);

  if (loading || !data) return <div className="space-y-4">{[...Array(6)].map((_, i) => <div key={i} className="h-24 bg-graphite rounded animate-pulse" />)}</div>;

  const g = data.global;
  const maxTrend = Math.max(...data.trend_mensual.map(t => t.total_leads), 1);

  return <div className="space-y-6">
    <h1 className="text-2xl font-[590] text-porcelain tracking-[-0.22px]">Funnel de Asignación</h1>
    <p className="text-storm-cloud text-sm -mt-4">¿Cuántos leads entran, cuántos se asignan, cuántos mueren en el agujero negro?</p>

    <div className="flex flex-wrap gap-3 items-end">
      <div><label className="block text-storm-cloud text-xs mb-1">Desde</label><input type="date" value={filters.fecha_desde} onChange={e => setFilters({ ...filters, fecha_desde: e.target.value })} className="bg-pitch-black border border-charcoal-grey rounded-md px-3 py-2 text-porcelain text-sm focus:border-neon-lime focus:outline-none" /></div>
      <div><label className="block text-storm-cloud text-xs mb-1">Hasta</label><input type="date" value={filters.fecha_hasta} onChange={e => setFilters({ ...filters, fecha_hasta: e.target.value })} className="bg-pitch-black border border-charcoal-grey rounded-md px-3 py-2 text-porcelain text-sm focus:border-neon-lime focus:outline-none" /></div>
      <div><label className="block text-storm-cloud text-xs mb-1">Fuente</label><select value={filters.fuente} onChange={e => setFilters({ ...filters, fuente: e.target.value })} className="bg-pitch-black border border-charcoal-grey rounded-md px-3 py-2 text-porcelain text-sm focus:border-neon-lime focus:outline-none"><option value="">Todas</option><option value="Botmaker">Botmaker</option><option value="ThinkChat">ThinkChat</option><option value="Manual">Manual</option></select></div>
    </div>

    {/* ── GLOBAL: THE BLACK HOLE ── */}
    <div className="grid grid-cols-4 gap-3">
      <div className="bg-graphite rounded-md p-4 border-l-2 border-neon-lime">
        <p className="text-storm-cloud text-[10px] uppercase">Total Leads</p>
        <p className="text-3xl font-[590] text-neon-lime mt-1">{g.total_leads.toLocaleString()}</p>
      </div>
      <div className="bg-graphite rounded-md p-4 border-l-2 border-emerald">
        <p className="text-storm-cloud text-[10px] uppercase">Asignados</p>
        <p className="text-3xl font-[590] text-emerald mt-1">{g.asignados.toLocaleString()}</p>
        <p className="text-fog-grey text-[10px] mt-1">{g.asignados_pct}% del total</p>
      </div>
      <div className="bg-graphite rounded-md p-4 border-l-2 border-warning-red">
        <p className="text-storm-cloud text-[10px] uppercase">Huérfanos</p>
        <p className="text-3xl font-[590] text-warning-red mt-1">{g.huerfanos_total.toLocaleString()}</p>
        <p className="text-fog-grey text-[10px] mt-1">{g.huerfanos_pct}% — SISTEMA: {g.sistema_epem.toLocaleString()} · Sin seller: {g.sin_seller.toLocaleString()}</p>
      </div>
      <div className="bg-graphite rounded-md p-4 border-l-2 border-aether-blue">
        <p className="text-storm-cloud text-[10px] uppercase">Gestionados</p>
        <p className="text-3xl font-[590] text-aether-blue mt-1">{g.gestionados.toLocaleString()}</p>
        <p className="text-fog-grey text-[10px] mt-1">{g.ventas.toLocaleString()} ventas</p>
      </div>
    </div>

    {/* ── VISUAL: ASIGNADOS VS HUÉRFANOS BAR ── */}
    <div className="bg-graphite rounded-md p-5">
      <h2 className="text-sm font-[590] text-porcelain mb-3">Asignación Global</h2>
      <div className="flex h-8 rounded-full overflow-hidden mb-2">
        <div className="bg-emerald h-full flex items-center justify-center text-[10px] text-pitch-black font-[590]" style={{ width: `${g.asignados_pct}%` }}>{g.asignados_pct}%</div>
        <div className="bg-warning-red h-full flex items-center justify-center text-[10px] text-pitch-black font-[590]" style={{ width: `${g.sistema_epem_pct}%` }}>SISTEMA {g.sistema_epem_pct}%</div>
        <div className="bg-storm-cloud/50 h-full flex items-center justify-center text-[10px] text-pitch-black font-[590]" style={{ width: `${g.sin_seller_pct}%` }}>{g.sin_seller_pct > 0 ? `∅ ${g.sin_seller_pct}%` : ""}</div>
      </div>
      <div className="flex justify-between text-[10px] text-fog-grey">
        <span>🟢 Asignados: {g.asignados.toLocaleString()}</span>
        <span>🔴 Huérfanos: {g.huerfanos_total.toLocaleString()} ({g.sistema_epem.toLocaleString()} en SISTEMA + {g.sin_seller.toLocaleString()} sin seller)</span>
      </div>
    </div>

    {/* ── POR UN ── */}
    <div className="bg-graphite rounded-md p-5">
      <h2 className="text-sm font-[590] text-porcelain mb-4">Asignación por Unidad de Negocio</h2>
      <div className="space-y-3">
        {data.por_un.filter(un => un.total_leads > 100).map(un => (
          <div key={un.enterprise_id}>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-light-steel">{un.un_nombre}</span>
              <span className="text-porcelain font-[590]">{un.total_leads.toLocaleString()} leads · {un.asignados_pct}% asignados · {un.huerfanos_pct}% huérfanos</span>
            </div>
            <div className="flex h-3 rounded-full overflow-hidden">
              <div className="bg-emerald h-full" style={{ width: `${un.asignados_pct}%` }} title={`Asignados: ${un.asignados_pct}%`} />
              <div className="bg-warning-red/70 h-full" style={{ width: `${un.huerfanos_pct}%` }} title={`Huérfanos: ${un.huerfanos_pct}%`} />
            </div>
          </div>
        ))}
      </div>
    </div>

    {/* ── POR FUENTE ── */}
    <div className="bg-graphite rounded-md p-5">
      <h2 className="text-sm font-[590] text-porcelain mb-4">Asignación por Fuente</h2>
      <div className="grid grid-cols-3 gap-3">
        {data.por_fuente.map(f => (
          <div key={f.fuente} className="bg-pitch-black rounded p-4">
            <p className="text-light-steel text-xs font-[510] mb-2">{f.fuente}</p>
            <p className="text-2xl font-[590] text-porcelain">{f.total_leads.toLocaleString()}</p>
            <div className="flex h-2 rounded-full overflow-hidden mt-2 mb-1">
              <div className="bg-emerald h-full" style={{ width: `${f.asignados_pct}%` }} />
              <div className="bg-warning-red/70 h-full" style={{ width: `${f.huerfanos_pct}%` }} />
            </div>
            <div className="flex justify-between text-[9px] text-fog-grey">
              <span>{f.asignados_pct}% asignados</span>
              <span>{f.huerfanos_pct}% huérfanos</span>
            </div>
            <p className="text-fog-grey text-[10px] mt-2">{f.gestionados.toLocaleString()} gestionados · {f.ventas.toLocaleString()} ventas</p>
          </div>
        ))}
      </div>
    </div>

    {/* ── POR SUPERVISOR ── */}
    <div className="bg-graphite rounded-md p-5">
      <h2 className="text-sm font-[590] text-porcelain mb-4">Leads Asignados por Supervisor</h2>
      <div className="grid grid-cols-4 gap-3">
        {data.por_supervisor.slice(0, 12).map(sup => (
          <div key={sup.supervisor_id} className="bg-pitch-black rounded p-3">
            <p className="text-light-steel text-xs font-[510] truncate" title={sup.supervisor_nombre}>{sup.supervisor_nombre}</p>
            <p className="text-lg font-[590] text-porcelain mt-1">{sup.leads_asignados.toLocaleString()}</p>
            <div className="flex justify-between text-[9px] text-fog-grey mt-1">
              <span>{sup.vendedores} vend.</span>
              <span>{sup.tasa_gestion}% gest.</span>
              <span>{sup.ventas} ventas</span>
            </div>
          </div>
        ))}
      </div>
    </div>

    {/* ── TREND MENSUAL ── */}
    <div className="bg-graphite rounded-md p-5">
      <h2 className="text-sm font-[590] text-porcelain mb-4">Trend Mensual de Asignación (12 meses)</h2>
      <div className="flex items-end gap-1 h-48">
        {data.trend_mensual.map((t, i) => (
          <div key={i} className="flex-1 flex flex-col items-center gap-1" title={`${t.mes_str}: ${t.total_leads.toLocaleString()} leads, ${t.asignados_pct}% asignados`}>
            <span className="text-[9px] text-storm-cloud">{t.total_leads >= 1000 ? `${(t.total_leads / 1000).toFixed(0)}k` : t.total_leads}</span>
            <div className="w-full flex flex-col rounded-t overflow-hidden" style={{ height: `${(t.total_leads / maxTrend) * 100}%`, minHeight: 4 }}>
              <div className="bg-emerald flex-1" style={{ height: `${t.asignados_pct}%` }} />
              <div className="bg-warning-red/70 flex-1" style={{ height: `${t.huerfanos_pct}%` }} />
            </div>
            <span className="text-[9px] text-fog-grey">{t.mes_str.slice(5)}</span>
          </div>
        ))}
      </div>
      <div className="flex justify-center gap-4 mt-2 text-[10px]">
        <span className="text-emerald">■ Asignados</span>
        <span className="text-warning-red">■ Huérfanos</span>
      </div>
    </div>
  </div>;
}
