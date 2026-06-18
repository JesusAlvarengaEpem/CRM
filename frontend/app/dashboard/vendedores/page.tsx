"use client";

import { useState, useEffect } from "react";

interface SellerRow { seller_id: number; fullname: string; leads: number; gestionados: number; ventas: number; conversion: number; cartera_caliente: number; cartera_fria: number; leads_prev?: number; gestionados_prev?: number; ventas_prev?: number; }

function Trend({ curr, prev }: { curr: number; prev?: number }) {
  if (!prev || prev===0) return null;
  const d = curr - prev; const pct = (d/prev)*100;
  const up = d>=0;
  return <span className={up?"text-emerald text-[10px] ml-1":"text-warning-red text-[10px] ml-1"}>
    {up?"+"+pct.toFixed(0):pct.toFixed(0)}%
  </span>;
}

export default function VendedoresPage() {
  const [data, setData] = useState<SellerRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState<keyof SellerRow>("ventas");
  const [sortDir, setSortDir] = useState<"asc"|"desc">("desc");
  const [f, setF] = useState({desde:"",hasta:"",un:"",fuente:"",status:"",campana:""});
  const [selected, setSelected] = useState<{seller:SellerRow; timeline:any[]}|null>(null);

  useEffect(()=>{
    const t=localStorage.getItem("token");if(!t)return;
    setLoading(true);
    let cancelled = false;
    const p=new URLSearchParams();
    if(f.desde)p.append("fecha_desde",f.desde);
    if(f.hasta)p.append("fecha_hasta",f.hasta);
    if(f.un)p.append("enterprise_id",f.un);
    if(f.fuente)p.append("fuente",f.fuente);
    if(f.status)p.append("status",f.status);
    if(f.campana)p.append("campaign_id",f.campana);
    const H={Authorization:"Bearer "+t};
    fetch("http://localhost:8000/api/dashboard/vendedores?"+p,{headers:H})
      .then(r=>r.json()).then(d=>{if(!cancelled){setData(d||[]);setLoading(false);}}).catch(()=>{if(!cancelled){setData([]);setLoading(false);}});
    return () => { cancelled = true; };
  },[f]);

  const loadDetail = async (seller:SellerRow) => {
    const t=localStorage.getItem("token");if(!t)return;
    const r=await fetch(`http://localhost:8000/api/dashboard/timeline?days=30`,{headers:{Authorization:"Bearer "+t}});
    setSelected({seller,timeline:r.ok?await r.json():[]});
  };

  const sorted=[...data].sort((a,b)=>{const av=a[sortBy]??0;const bv=b[sortBy]??0;return sortDir==="desc"?Number(bv)-Number(av):Number(av)-Number(bv)});
  const hs=(col:keyof SellerRow)=>{if(sortBy===col)setSortDir(sortDir==="desc"?"asc":"desc");else{setSortBy(col);setSortDir("desc")}};

  return <div className="space-y-6">
    <div className="flex justify-between"><div><h1 className="text-2xl font-[590] text-porcelain tracking-[-0.22px]">Ranking Vendedores</h1><p className="text-storm-cloud text-sm mt-1">Click en vendedor para ver detalle</p></div></div>

    <div className="flex flex-wrap gap-2 items-end">
      <div><label className="block text-storm-cloud text-[10px] mb-0.5">Desde</label><input type="date" value={f.desde} onChange={e=>setF({...f,desde:e.target.value})} className="bg-pitch-black border border-charcoal-grey rounded px-2 py-1.5 text-porcelain text-xs focus:border-neon-lime focus:outline-none w-32"/></div>
      <div><label className="block text-storm-cloud text-[10px] mb-0.5">Hasta</label><input type="date" value={f.hasta} onChange={e=>setF({...f,hasta:e.target.value})} className="bg-pitch-black border border-charcoal-grey rounded px-2 py-1.5 text-porcelain text-xs focus:border-neon-lime focus:outline-none w-32"/></div>
      <div><label className="block text-storm-cloud text-[10px] mb-0.5">UN</label><select value={f.un} onChange={e=>setF({...f,un:e.target.value})} className="bg-pitch-black border border-charcoal-grey rounded px-2 py-1.5 text-porcelain text-xs focus:border-neon-lime focus:outline-none"><option value="">Todas</option><option value="1">Odontologia</option><option value="2">Med. Prepaga</option><option value="4">Emergencias</option><option value="5">Med. Estetica</option></select></div>
      <div><label className="block text-storm-cloud text-[10px] mb-0.5">Fuente</label><select value={f.fuente} onChange={e=>setF({...f,fuente:e.target.value})} className="bg-pitch-black border border-charcoal-grey rounded px-2 py-1.5 text-porcelain text-xs focus:border-neon-lime focus:outline-none"><option value="">Todas</option><option value="Botmaker">Botmaker</option><option value="ThinkChat">ThinkChat</option><option value="Manual">Manual</option></select></div>
      <div><label className="block text-storm-cloud text-[10px] mb-0.5">Status</label><select value={f.status} onChange={e=>setF({...f,status:e.target.value})} className="bg-pitch-black border border-charcoal-grey rounded px-2 py-1.5 text-porcelain text-xs focus:border-neon-lime focus:outline-none"><option value="">Todos</option><option value="1">Nuevo</option><option value="5">Contactado</option><option value="10">Gestionado</option><option value="15">Cerrado</option><option value="30">Perdido</option></select></div>
    </div>

    <div className="bg-graphite rounded-md shadow-[rgba(0,0,0,0.4)_0px_2px_4px_0px] overflow-hidden">
      <table className="w-full text-xs">
        <thead><tr className="border-b border-charcoal-grey text-storm-cloud font-[510]">
          {[{k:"seller_id",l:"#",w:"w-12"},{k:"fullname",l:"Vendedor",w:""},{k:"leads",l:"Leads",w:"w-20"},{k:"gestionados",l:"Gestionad.",w:"w-20"},{k:"ventas",l:"Ventas",w:"w-16"},{k:"conversion",l:"%",w:"w-12"},{k:"cartera_caliente",l:"Caliente",w:"w-16"},{k:"cartera_fria",l:"Fria",w:"w-14"}].map(col=>
            <th key={col.k} onClick={()=>hs(col.k)} className={`px-3 py-2 text-left cursor-pointer hover:text-light-steel select-none ${col.w}`}>
              {col.l}{sortBy===col.k&&<span className="ml-0.5 text-porcelain">{sortDir==="desc"?"v":"^"}</span>}
            </th>
          )}</tr></thead>
        <tbody>
          {loading?[...Array(12)].map((_,i)=><tr key={i} className="border-b border-charcoal-grey">{[...Array(8)].map((_,j)=><td key={j} className="px-3 py-2"><div className="h-3 bg-charcoal-grey rounded animate-pulse"/></td>)}</tr>):
          sorted.map(row=>
            <tr key={row.seller_id} onClick={()=>loadDetail(row)} className="border-b border-charcoal-grey/50 hover:bg-deep-slate/50 transition-colors cursor-pointer">
              <td className="px-3 py-2 text-fog-grey">{row.seller_id}</td>
              <td className="px-3 py-2 text-porcelain font-[510]">{row.fullname}</td>
              <td className="px-3 py-2 text-light-steel">{row.leads.toLocaleString()}<Trend curr={row.leads} prev={row.leads_prev}/></td>
              <td className="px-3 py-2 text-light-steel">{row.gestionados.toLocaleString()}<Trend curr={row.gestionados} prev={row.gestionados_prev}/></td>
              <td className="px-3 py-2 text-porcelain font-[590]">{row.ventas.toLocaleString()}<Trend curr={row.ventas} prev={row.ventas_prev}/></td>
              <td className="px-3 py-2"><span className={row.conversion>=10?"text-emerald":"text-storm-cloud"}>{row.conversion.toFixed(1)}%</span></td>
              <td className="px-3 py-2 text-cyan-spark">{row.cartera_caliente.toLocaleString()}</td>
              <td className="px-3 py-2 text-fog-grey">{row.cartera_fria.toLocaleString()}</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>

    {selected&&<div className="bg-graphite rounded-md p-5 border-l-2 border-neon-lime">
      <div className="flex justify-between"><h2 className="font-[590] text-porcelain">{selected.seller.fullname} — ID {selected.seller.seller_id}</h2><button onClick={()=>setSelected(null)} className="text-storm-cloud hover:text-porcelain text-xs">Cerrar</button></div>
      <div className="grid grid-cols-4 gap-3 mt-3">
        <div className="bg-pitch-black rounded p-3"><p className="text-fog-grey text-[10px]">Leads</p><p className="text-porcelain font-[590]">{selected.seller.leads.toLocaleString()}</p></div>
        <div className="bg-pitch-black rounded p-3"><p className="text-fog-grey text-[10px]">Ventas</p><p className="text-porcelain font-[590]">{selected.seller.ventas.toLocaleString()}</p></div>
        <div className="bg-pitch-black rounded p-3"><p className="text-fog-grey text-[10px]">% Conv</p><p className="text-porcelain font-[590]">{selected.seller.conversion.toFixed(1)}%</p></div>
        <div className="bg-pitch-black rounded p-3"><p className="text-fog-grey text-[10px]">Caliente</p><p className="text-cyan-spark font-[590]">{selected.seller.cartera_caliente.toLocaleString()}</p></div>
      </div>
      {selected.timeline.length>0&&<div className="mt-3 flex items-end gap-0.5 h-16">
        {selected.timeline.map((p:any,i:number)=><div key={i} className="flex-1 bg-aether-blue rounded-t" style={{height:`${(p.leads/Math.max(...selected.timeline.map((x:any)=>x.leads),1))*100}%`,minHeight:2}} title={`${p.dia}: ${p.leads} leads`}/>)}
      </div>}
    </div>}
  </div>;
}

