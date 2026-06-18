"use client";

import { useState, useEffect } from "react";

interface HomeData {
  leads_nuevos: number; leads_nuevos_prev: number;
  gestionados: number; gestionados_prev: number;
  ventas: number; ventas_prev: number;
  conversion: number; conversion_prev: number;
  tasa_contacto: number; tasa_contacto_prev: number;
}
interface ExtendedData {
  por_fuente: { fuente: string; leads: number; gestionados: number; ventas: number }[];
  por_un: { enterprise_id: number; leads: number; ventas: number }[];
  pipeline_velocity: { avg_hours: number; contacted: number };
  leads_perdidos: number;
  leads_hoy: number;
}
interface TimelinePoint { dia: string; leads: number; gestionados: number; ventas: number }

const UN_MAP: Record<number,string> = {1:"Odontologia",2:"Med. Prepaga",4:"Emergencias",5:"Med. Estetica"};

function Trend({curr,prev,suffix}:{curr:number;prev:number;suffix?:string}){
  if(!prev)return null;
  const d=curr-prev; const pct=prev>0?(d/prev*100).toFixed(0):"0";
  const up=d>=0;
  return <span className={`text-xs font-[590] ${up?"text-emerald":"text-warning-red"}`}>{up?"+"+pct:pct}%</span>;
}

export default function HomePage() {
  const [data,setData]=useState<HomeData|null>(null);
  const [ext,setExt]=useState<ExtendedData|null>(null);
  const [timeline,setTimeline]=useState<TimelinePoint[]>([]);
  const [loading,setLoading]=useState(true);
  const [f,setF]=useState({desde:"2026-06-01",hasta:"2026-06-04",un:"",fuente:""});

  useEffect(()=>{
    const t=localStorage.getItem("token");if(!t)return;
    const p=new URLSearchParams();
    if(f.desde)p.append("fecha_desde",f.desde);
    if(f.hasta)p.append("fecha_hasta",f.hasta);
    if(f.un)p.append("enterprise_id",f.un);
    if(f.fuente)p.append("fuente",f.fuente);
    const H={Authorization:"Bearer "+t};
    Promise.all([
      fetch("http://localhost:8000/api/dashboard/home?"+p,{headers:H}).then(r=>r.json()),
      fetch("http://localhost:8000/api/dashboard/home-extended?"+p,{headers:H}).then(r=>r.json()),
      fetch("http://localhost:8000/api/dashboard/timeline?days=7",{headers:H}).then(r=>r.json()),
    ]).then(([h,e,tl])=>{setData(h);setExt(e);setTimeline(tl||[]);setLoading(false);}).catch(()=>setLoading(false));
  },[f]);

  if(loading||!data)return <div className="space-y-4">{[...Array(8)].map((_,i)=><div key={i} className="h-16 bg-graphite rounded-md animate-pulse"/>)}</div>;

  const maxTL=Math.max(...timeline.map(p=>p.leads),1);
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-[590] text-porcelain tracking-[-0.22px]">Home</h1><p className="text-storm-cloud text-sm mt-1">Command Center — KPIs</p></div>
        <div className="flex gap-3">
          <input type="date" value={f.desde} onChange={e=>setF({...f,desde:e.target.value})} className="bg-pitch-black border border-charcoal-grey rounded-md px-3 py-2 text-porcelain text-sm focus:border-neon-lime focus:outline-none"/>
          <input type="date" value={f.hasta} onChange={e=>setF({...f,hasta:e.target.value})} className="bg-pitch-black border border-charcoal-grey rounded-md px-3 py-2 text-porcelain text-sm focus:border-neon-lime focus:outline-none"/>
        </div>
      </div>

      {/* KPIs Row 1 */}
      <div className="grid grid-cols-5 gap-3">
        {[{l:"Leads",c:data.leads_nuevos,p:data.leads_nuevos_prev,cl:"border-l-aether-blue"},
          {l:"Gestionados",c:data.gestionados,p:data.gestionados_prev,cl:"border-l-cyan-spark"},
          {l:"Ventas",c:data.ventas,p:data.ventas_prev,cl:"border-l-emerald"},
          {l:"% Conversion",c:data.conversion,p:data.conversion_prev,cl:"border-l-deep-violet",s:"%"},
          {l:"% Contacto",c:data.tasa_contacto,p:data.tasa_contacto_prev,cl:"border-l-amethyst",s:"%"}].map((k,i)=>(
          <div key={i} className={`bg-graphite rounded-md p-4 border-l-2 ${k.cl}`}>
            <p className="text-storm-cloud text-[11px] uppercase tracking-wider">{k.l}</p>
            <div className="flex items-baseline gap-2 mt-1"><span className="text-2xl font-[590] text-porcelain">{k.c.toLocaleString()}{k.s||""}</span><Trend curr={k.c} prev={k.p} suffix={k.s}/></div>
            <p className="text-fog-grey text-[10px] mt-1">vs {k.p.toLocaleString()}{k.s||""} prev</p>
          </div>
        ))}
      </div>

      {/* KPIs Row 2 */}
      {ext&&<div className="grid grid-cols-3 gap-3">
        <div className="bg-graphite rounded-md p-4">
          <p className="text-storm-cloud text-[11px] uppercase tracking-wider">Leads Hoy</p>
          <p className="text-2xl font-[590] text-aether-blue mt-1">{ext.leads_hoy.toLocaleString()}</p>
        </div>
        <div className="bg-graphite rounded-md p-4">
          <p className="text-storm-cloud text-[11px] uppercase tracking-wider">Pipeline Velocity</p>
          <p className="text-2xl font-[590] text-cyan-spark mt-1">{ext.pipeline_velocity.avg_hours}h</p>
          <p className="text-fog-grey text-[10px] mt-1">{ext.pipeline_velocity.contacted.toLocaleString()} leads contactados</p>
        </div>
        <div className="bg-graphite rounded-md p-4">
          <p className="text-storm-cloud text-[11px] uppercase tracking-wider">Perdidos</p>
          <p className="text-2xl font-[590] text-warning-red mt-1">{ext.leads_perdidos.toLocaleString()}</p>
        </div>
      </div>}

      {/* Timeline */}
      {timeline.length>0&&<div className="bg-graphite rounded-md p-5">
        <h2 className="text-sm font-[590] text-porcelain mb-4">Timeline — Ultimos 7 dias</h2>
        <div className="flex items-end gap-1 h-32">
          {timeline.map((p,i)=>(<div key={i} className="flex-1 flex flex-col items-center gap-1" title={`${p.dia}: ${p.leads} leads`}>
            <span className="text-[10px] text-storm-cloud">{p.leads}</span>
            <div className="w-full bg-aether-blue rounded-t" style={{height:`${(p.leads/maxTL)*100}%`,minHeight:2}}/>
            <span className="text-[9px] text-fog-grey">{p.dia.slice(5)}</span>
          </div>))}
        </div>
      </div>}

      {/* Sources and UN breakdown */}
      {ext&&<div className="grid grid-cols-2 gap-4">
        <div className="bg-graphite rounded-md p-5">
          <h2 className="text-sm font-[590] text-porcelain mb-3">Por Fuente</h2>
          <div className="space-y-2">
            {ext.por_fuente.map(s=>(<div key={s.fuente} className="flex items-center justify-between text-sm">
              <span className="text-light-steel">{s.fuente}</span>
              <div className="flex gap-3 text-right"><span className="text-porcelain font-[590]">{s.leads.toLocaleString()}</span><span className="text-emerald text-xs">{s.ventas} ventas</span></div>
            </div>))}
          </div>
        </div>
        <div className="bg-graphite rounded-md p-5">
          <h2 className="text-sm font-[590] text-porcelain mb-3">Por UN</h2>
          <div className="space-y-2">
            {ext.por_un.map(u=>(<div key={u.enterprise_id} className="flex items-center justify-between text-sm">
              <span className="text-light-steel">{UN_MAP[u.enterprise_id]||u.enterprise_id}</span>
              <div className="flex gap-3 text-right"><span className="text-porcelain font-[590]">{u.leads.toLocaleString()}</span><span className="text-emerald text-xs">{u.ventas} ventas</span></div>
            </div>))}
          </div>
        </div>
      </div>}
    </div>
  );
}

