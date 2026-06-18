"use client";

import { useState, useEffect } from "react";

interface CampanaRow {
  campaign_id: number;
  campaign_name: string;
  leads: number; leads_prev: number;
  ventas: number; ventas_prev: number;
  conversion: number;
}

function T({ curr, prev }: { curr: number; prev?: number }) {
  if (prev === undefined) return null;
  if (prev === 0 && curr === 0) return <span className="text-fog-grey text-[10px]">—</span>;
  if (prev === 0) return <span className="text-emerald text-[10px]">+∞</span>;
  const d = curr - prev;
  const pct = ((d / prev) * 100).toFixed(0);
  const up = d >= 0;
  return <span className={up ? "text-emerald text-[10px] ml-1" : "text-warning-red text-[10px] ml-1"}>{up ? "+" + pct : pct}%</span>;
}

export default function CampanasPage() {
  const [data, setData] = useState<CampanaRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [f, setF] = useState({ desde: "", hasta: "", un: "", fuente: "" });

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) return;
    const p = new URLSearchParams();
    if (f.desde) p.append("fecha_desde", f.desde);
    if (f.hasta) p.append("fecha_hasta", f.hasta);
    if (f.un) p.append("enterprise_id", f.un);
    if (f.fuente) p.append("fuente", f.fuente);
    fetch("http://localhost:8000/api/dashboard/campanas?" + p, {
      headers: { Authorization: "Bearer " + token },
    })
      .then((r) => r.json())
      .then((d) => {
        setData(d || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [f]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-[590] text-porcelain tracking-[-0.22px]">Top Campañas</h1>
        <p className="text-storm-cloud text-sm mt-1">Ranking con △% vs período anterior</p>
      </div>

      <div className="flex flex-wrap gap-2 items-end">
        <div><label className="block text-storm-cloud text-[10px] mb-0.5">Desde</label><input type="date" value={f.desde} onChange={(e) => setF({ ...f, desde: e.target.value })} className="bg-pitch-black border border-charcoal-grey rounded px-2 py-1.5 text-porcelain text-xs focus:border-neon-lime focus:outline-none w-32" /></div>
        <div><label className="block text-storm-cloud text-[10px] mb-0.5">Hasta</label><input type="date" value={f.hasta} onChange={(e) => setF({ ...f, hasta: e.target.value })} className="bg-pitch-black border border-charcoal-grey rounded px-2 py-1.5 text-porcelain text-xs focus:border-neon-lime focus:outline-none w-32" /></div>
        <div><label className="block text-storm-cloud text-[10px] mb-0.5">UN</label><select value={f.un} onChange={(e) => setF({ ...f, un: e.target.value })} className="bg-pitch-black border border-charcoal-grey rounded px-2 py-1.5 text-porcelain text-xs focus:border-neon-lime focus:outline-none"><option value="">Todas</option><option value="1">Odontologia</option><option value="2">Med. Prepaga</option><option value="4">Emergencias</option><option value="5">Med. Estetica</option></select></div>
        <div><label className="block text-storm-cloud text-[10px] mb-0.5">Fuente</label><select value={f.fuente} onChange={(e) => setF({ ...f, fuente: e.target.value })} className="bg-pitch-black border border-charcoal-grey rounded px-2 py-1.5 text-porcelain text-xs focus:border-neon-lime focus:outline-none"><option value="">Todas</option><option value="Botmaker">Botmaker</option><option value="ThinkChat">ThinkChat</option><option value="Manual">Manual</option></select></div>
      </div>

      <div className="bg-graphite rounded-md shadow-[rgba(0,0,0,0.4)_0px_2px_4px_0px] overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-charcoal-grey text-storm-cloud font-[510]">
              <th className="px-3 py-2 text-left w-10">#</th>
              <th className="px-3 py-2 text-left">Campaña</th>
              <th className="px-3 py-2 text-right w-20">Leads</th>
              <th className="px-3 py-2 text-right w-20">Ventas</th>
              <th className="px-3 py-2 text-right w-16">% Conv.</th>
            </tr>
          </thead>
          <tbody>
            {loading
              ? [...Array(10)].map((_, i) => (
                  <tr key={i} className="border-b border-charcoal-grey">
                    {[...Array(5)].map((_, j) => (
                      <td key={j} className="px-3 py-2"><div className="h-3 bg-charcoal-grey rounded animate-pulse" /></td>
                    ))}
                  </tr>
                ))
              : data.map((row, idx) => (
                  <tr key={row.campaign_id} className="border-b border-charcoal-grey/50 hover:bg-deep-slate/50 transition-colors">
                    <td className="px-3 py-2 text-fog-grey text-[10px]">{idx + 1}</td>
                    <td className="px-3 py-2 text-aether-blue font-[510]">{row.campaign_name}</td>
                    <td className="px-3 py-2 text-right text-light-steel">{row.leads.toLocaleString()}<T curr={row.leads} prev={row.leads_prev} /></td>
                    <td className="px-3 py-2 text-right text-porcelain font-[590]">{row.ventas.toLocaleString()}<T curr={row.ventas} prev={row.ventas_prev} /></td>
                    <td className="px-3 py-2 text-right"><span className={row.conversion >= 5 ? "text-emerald" : "text-storm-cloud"}>{row.conversion}%</span></td>
                  </tr>
                ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

