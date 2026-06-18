"use client";

import { useState, useEffect } from "react";

export default function PipelinePage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) return;
    Promise.all([
      fetch("http://localhost:8000/api/dashboard/home-extended", { headers: { Authorization: `Bearer ${token}` } }).then(r => r.json()),
      fetch("http://localhost:8000/api/dashboard/timeline?days=7", { headers: { Authorization: `Bearer ${token}` } }).then(r => r.json()),
    ]).then(([ext, tl]) => { setData({ ext, tl }); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  if (loading || !data) return <div className="space-y-4">{[...Array(4)].map((_,i)=><div key={i} className="h-16 bg-graphite rounded animate-pulse"/>)}</div>;

  const { ext, tl } = data;
  const maxTl = Math.max(...tl.map((t:any) => t.leads), 1);
  const maxFuente = Math.max(...ext.por_fuente.map((f:any) => f.leads), 1);
  const totalContacted = ext.pipeline_velocity?.contacted || 0;
  const totalLeads = ext.por_fuente.reduce((s:number,f:any) => s+f.leads, 0) || 1;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-[590] text-porcelain tracking-[-0.22px]">Pipeline Velocity</h1>
        <p className="text-storm-cloud text-sm mt-1">Velocidad del pipeline y distribucion por fuente</p>
      </div>

      <div className="grid grid-cols-4 gap-3">
        <div className="bg-graphite rounded-md p-4 border-l-2 border-emerald">
          <p className="text-storm-cloud text-[10px] uppercase">Avg Time to Contact</p>
          <p className="text-4xl font-[590] text-emerald mt-2">{ext.pipeline_velocity?.avg_hours || 0}h</p>
          <p className="text-fog-grey text-[10px] mt-1">desde first_seen</p>
        </div>
        <div className="bg-graphite rounded-md p-4 border-l-2 border-aether-blue">
          <p className="text-storm-cloud text-[10px] uppercase">Contact Rate</p>
          <p className="text-4xl font-[590] text-aether-blue mt-2">{totalLeads > 0 ? ((totalContacted/totalLeads)*100).toFixed(1) : 0}%</p>
          <p className="text-fog-grey text-[10px] mt-1">{totalContacted.toLocaleString()} de {totalLeads.toLocaleString()}</p>
        </div>
        <div className="bg-graphite rounded-md p-4 border-l-2 border-deep-violet">
          <p className="text-storm-cloud text-[10px] uppercase">Leads Perdidos</p>
          <p className="text-4xl font-[590] text-deep-violet mt-2">{ext.leads_perdidos?.toLocaleString()}</p>
          <p className="text-fog-grey text-[10px] mt-1">status=30</p>
        </div>
        <div className="bg-graphite rounded-md p-4 border-l-2 border-neon-lime">
          <p className="text-storm-cloud text-[10px] uppercase">Leads Hoy</p>
          <p className="text-4xl font-[590] text-neon-lime mt-2">{ext.leads_hoy?.toLocaleString()}</p>
          <p className="text-fog-grey text-[10px] mt-1">ultimas 24h</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-graphite rounded-md p-5">
          <h2 className="text-sm font-[590] text-porcelain mb-4">Daily Leads - 7d</h2>
          <div className="flex items-end gap-1 h-32">
            {tl.map((p:any,i:number) => (
              <div key={i} className="flex-1 flex flex-col items-center gap-1" title={`${p.dia}: ${p.leads} leads`}>
                <span className="text-[10px] text-storm-cloud">{p.leads}</span>
                <div className="w-full bg-aether-blue rounded-t" style={{height:`${(p.leads/maxTl)*100}%`,minHeight:2}}/>
                <span className="text-[9px] text-fog-grey">{p.dia?.slice(5)}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="bg-graphite rounded-md p-5">
          <h2 className="text-sm font-[590] text-porcelain mb-4">Por Fuente</h2>
          <div className="space-y-3">
            {ext.por_fuente?.map((f:any) => (
              <div key={f.fuente}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-light-steel">{f.fuente}</span>
                  <span className="text-porcelain font-[590]">{f.leads.toLocaleString()} leads · {f.ventas} ventas</span>
                </div>
                <div className="h-2 bg-pitch-black rounded-full overflow-hidden">
                  <div className="h-full rounded-full bg-aether-blue/70" style={{width:`${(f.leads/maxFuente)*100}%`}}/>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="bg-graphite rounded-md p-5">
        <h2 className="text-sm font-[590] text-porcelain mb-4">Por UN</h2>
        <div className="grid grid-cols-2 gap-4">
          {ext.por_un?.map((u:any) => (
            <div key={u.enterprise_id} className="bg-pitch-black rounded p-3 flex justify-between items-center">
              <span className="text-light-steel text-sm">UN {u.enterprise_id}</span>
              <span className="text-porcelain font-[590] text-sm">{u.leads.toLocaleString()} leads · {u.ventas} ventas</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

