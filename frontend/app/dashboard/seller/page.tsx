"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";

interface SellerTimeline { dia: string; leads: number; gestionados: number; ventas: number }
interface SellerStats { seller_id: number; fullname: string; leads: number; gestionados: number; ventas: number; conversion: number; cartera_caliente: number; cartera_fria: number; leads_prev: number; ventas_prev: number; gestionados_prev: number }

function SellerContent() {
  const searchParams = useSearchParams();
  const sellerId = searchParams.get("id");
  const [stats, setStats] = useState<SellerStats | null>(null);
  const [timeline, setTimeline] = useState<SellerTimeline[]>([]);
  const [loading, setLoading] = useState(true);
  const [fuente, setFuente] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("token"); if (!token || !sellerId) return;
    const params = new URLSearchParams();
    params.append("enterprise_id", "");
    params.append("fecha_desde", "2026-05-01");
    params.append("fecha_hasta", "2026-05-31");
    if (fuente) params.append("fuente", fuente);
    const tlParams = new URLSearchParams();
    tlParams.append("days", "30");
    if (fuente) tlParams.append("fuente", fuente);
    Promise.all([
      fetch(`http://localhost:8000/api/dashboard/vendedores?${params}`, { headers: { Authorization: `Bearer ${token}` } }).then(r => r.json()),
      fetch(`http://localhost:8000/api/dashboard/timeline?${tlParams}`, { headers: { Authorization: `Bearer ${token}` } }).then(r => r.json()),
    ]).then(([sellers, tl]) => {
      const found = sellers.find((s: any) => s.seller_id === parseInt(sellerId));
      setStats(found || null);
      setTimeline(tl || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [sellerId, fuente]);

  if (!sellerId) return <div className="text-storm-cloud text-sm p-8">Selecciona un vendedor desde la tabla de Vendedores.</div>;
  if (loading) return <div className="space-y-4">{[...Array(5)].map((_,i)=><div key={i} className="h-16 bg-graphite rounded animate-pulse"/>)}</div>;
  if (!stats) return <div className="text-warning-red p-8">Vendedor no encontrado</div>;

  const maxTL = Math.max(...timeline.map(t => t.leads), 1);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-[590] text-porcelain tracking-[-0.22px]">{stats.fullname}</h1>
          <p className="text-storm-cloud text-xs mt-1">Vendedor #{stats.seller_id}</p>
        </div>
        <div>
          <label className="block text-storm-cloud text-[10px] mb-0.5">Fuente</label>
          <select value={fuente} onChange={(e) => setFuente(e.target.value)} className="bg-pitch-black border border-charcoal-grey rounded px-2 py-1.5 text-porcelain text-xs focus:border-neon-lime focus:outline-none">
            <option value="">Todas</option>
            <option value="Botmaker">Botmaker</option>
            <option value="ThinkChat">ThinkChat</option>
            <option value="Manual">Manual</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-5 gap-3">
        <div className="bg-graphite rounded-md p-4 border-l-2 border-aether-blue">
          <p className="text-storm-cloud text-[10px] uppercase">Leads</p>
          <p className="text-2xl font-[590] text-aether-blue mt-1">{stats.leads.toLocaleString()}</p>
          {stats.leads_prev > 0 && <p className={`text-xs mt-1 ${stats.leads > stats.leads_prev ? "text-emerald" : "text-warning-red"}`}>{stats.leads > stats.leads_prev ? "+" : ""}{((stats.leads - stats.leads_prev)/stats.leads_prev*100).toFixed(0)}%</p>}
        </div>
        <div className="bg-graphite rounded-md p-4 border-l-2 border-cyan-spark">
          <p className="text-storm-cloud text-[10px] uppercase">Gestionados</p>
          <p className="text-2xl font-[590] text-cyan-spark mt-1">{stats.gestionados.toLocaleString()}</p>
        </div>
        <div className="bg-graphite rounded-md p-4 border-l-2 border-emerald">
          <p className="text-storm-cloud text-[10px] uppercase">Ventas</p>
          <p className="text-2xl font-[590] text-emerald mt-1">{stats.ventas.toLocaleString()}</p>
          {stats.ventas_prev > 0 && <p className={`text-xs mt-1 ${stats.ventas > stats.ventas_prev ? "text-emerald" : "text-warning-red"}`}>{stats.ventas > stats.ventas_prev ? "+" : ""}{((stats.ventas - stats.ventas_prev)/stats.ventas_prev*100).toFixed(0)}%</p>}
        </div>
        <div className="bg-graphite rounded-md p-4 border-l-2 border-deep-violet">
          <p className="text-storm-cloud text-[10px] uppercase">% Conversion</p>
          <p className="text-2xl font-[590] text-deep-violet mt-1">{stats.conversion.toFixed(1)}%</p>
        </div>
        <div className="bg-graphite rounded-md p-4">
          <p className="text-storm-cloud text-[10px] uppercase">Cartera</p>
          <div className="mt-1 space-y-1 text-xs">
            <div className="flex justify-between"><span className="text-cyan-spark">Caliente</span><span className="text-porcelain font-[590]">{stats.cartera_caliente.toLocaleString()}</span></div>
            <div className="flex justify-between"><span className="text-fog-grey">Fria</span><span className="text-porcelain font-[590]">{stats.cartera_fria.toLocaleString()}</span></div>
          </div>
        </div>
      </div>

      {timeline.length > 0 && (
        <div className="bg-graphite rounded-md p-5">
          <h2 className="text-sm font-[590] text-porcelain mb-4">Actividad — Últimos 30 días</h2>
          <div className="flex items-end gap-1 h-32">
            {timeline.map((p, i) => (
              <div key={i} className="flex-1 flex flex-col items-center gap-1" title={`${p.dia}: ${p.leads} leads`}>
                <span className="text-[10px] text-storm-cloud">{p.leads}</span>
                <div className="w-full bg-aether-blue rounded-t" style={{ height: `${(p.leads / maxTL) * 100}%`, minHeight: 2 }} />
                <span className="text-[9px] text-fog-grey">{p.dia.slice(5)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function SellerPage() {
  return (
    <Suspense fallback={<div className="space-y-4">{[...Array(5)].map((_,i)=><div key={i} className="h-16 bg-graphite rounded animate-pulse"/>)}</div>}>
      <SellerContent />
    </Suspense>
  );
}

