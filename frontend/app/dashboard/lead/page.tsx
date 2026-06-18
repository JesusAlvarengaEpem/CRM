"use client";

import { useState } from "react";

interface LeadHistory {
  id: number; phone: string; fullname: string; status: number;
  enterprise_id: number; seller: string; closer?: string | null;
  contract_id: number | null;
  lead_source: string | null; observation: string | null;
  form_id: number | null; ad_id: number | null; ad_set_id: number | null;
  city_id: number | null; deadline: string; notificated: string | null;
  scheduled: string | null;
  created_at: string; updated_at: string; closed_at: string; selled_at: string;
  rejected_at: string; rejected_motive_id: number | null;
  tracking_history: {
    timestamp: string; status: number; observation: string; agent: string;
    attended: boolean; sold: boolean; reject: boolean; closer: boolean;
    reassigned: boolean; contact_form: number; call_again: string | null;
    scheduled_time: string | null;
  }[];
}
interface LeadResult {
  query: string;
  dw_matches: any[];
  epem_historial: LeadHistory[];
  epem_error: string | null;
}

const STATUS_MAP: Record<number, string> = { 1: "Nuevo", 5: "Contactado", 10: "Gestionado", 15: "Cerrado", 30: "Perdido" };
const UN_MAP: Record<number, string> = { 1: "Odontologia", 2: "Med. Prepaga", 4: "Emergencias", 5: "Med. Estetica" };
const FUENTE_COLORS: Record<string, string> = {
  ThinkChat: "bg-emerald/20 text-emerald",
  Botmaker: "bg-aether-blue/20 text-aether-blue",
  Manual: "bg-fog-grey/20 text-light-steel",
  DW: "bg-deep-violet/20 text-deep-violet",
  EPEM: "bg-cyan-spark/20 text-cyan-spark",
};

function fmt(d: string | null | undefined): string {
  if (!d || d === "None" || d === "null") return "—";
  return d.replace("T", " ").slice(0, 16);
}

function daysBetween(d1: string, d2: string | null): number {
  if (!d2) return 0;
  const a = new Date(d1).getTime();
  const b = new Date(d2).getTime();
  return Math.max(0, Math.round((b - a) / 86400000));
}

function Timeline({ h }: { h: LeadHistory }) {
  const events: { date: string; label: string; color: string; dot: string; detail: string }[] = [];

  if (h.tracking_history && h.tracking_history.length > 0) {
    h.tracking_history.forEach((t: any) => {
      let label = "Contacto";
      let color = "text-cyan-spark";
      let dot = "bg-cyan-spark";
      if (t.sold) { label = "Vendido"; color = "text-emerald"; dot = "bg-emerald"; }
      else if (t.reject) { label = "Rechazado"; color = "text-warning-red"; dot = "bg-warning-red"; }
      else if (t.closer) { label = "Cerrador asignado"; color = "text-deep-violet"; dot = "bg-deep-violet"; }
      else if (t.reassigned) { label = "Reasignado"; color = "text-amber-300"; dot = "bg-amber-300"; }
      else if (t.attended) { label = "Atendido"; color = "text-aether-blue"; dot = "bg-aether-blue"; }
      events.push({
        date: t.timestamp,
        label,
        color,
        dot,
        detail: t.observation || (t.agent ? `Agente: ${t.agent}` : ""),
      });
    });
  } else {
    if (h.created_at) events.push({ date: h.created_at, label: "Creado", color: "text-storm-cloud", dot: "bg-storm-cloud", detail: "" });
    if (h.selled_at && h.selled_at !== "None") events.push({ date: h.selled_at, label: "Vendido", color: "text-emerald", dot: "bg-emerald", detail: "" });
  }

  return (
    <div className="relative pl-6">
      <div className="absolute left-2 top-2 bottom-2 w-px bg-charcoal-grey" />
      {events.map((e, i) => (
        <div key={i} className="relative pb-3 last:pb-0">
          <div className={`absolute left-[3px] top-1 w-2 h-2 rounded-full ${e.dot}`} />
          <div className="text-[11px] text-fog-grey">{fmt(e.date)}</div>
          <div className={`text-xs font-[510] ${e.color}`}>{e.label}</div>
          {e.detail && <div className="text-[10px] text-fog-grey mt-0.5 leading-tight max-w-[180px] truncate">{e.detail}</div>}
        </div>
      ))}
    </div>
  );
}

export default function LeadTrackPage() {
  const [query, setQuery] = useState("");
  const [fuente, setFuente] = useState("");
  const [data, setData] = useState<LeadResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const search = async () => {
    if (!query.trim()) return;
    setLoading(true); setError("");
    try {
      const token = localStorage.getItem("token");
      let url = `http://localhost:8000/api/dashboard/lead?q=${encodeURIComponent(query.trim())}`;
      if (fuente) url += `&fuente=${encodeURIComponent(fuente)}`;
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Error en busqueda");
      setData(await res.json());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-[590] text-porcelain tracking-[-0.22px]">Lead Track</h1>
      <p className="text-storm-cloud text-sm -mt-4">Cruce DW (PostgreSQL) ↔ EPEM (MySQL) — buscar por telefono o nombre</p>

      <div className="flex gap-3 max-w-2xl">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
          placeholder="0992746761 o nombre..."
          className="flex-1 bg-pitch-black border border-charcoal-grey rounded-md px-3.5 py-3 text-porcelain text-sm focus:border-neon-lime focus:outline-none"
        />
        <select value={fuente} onChange={(e) => setFuente(e.target.value)} className="bg-pitch-black border border-charcoal-grey rounded-md px-3 py-3 text-porcelain text-sm focus:border-neon-lime focus:outline-none">
          <option value="">Todas fuentes</option>
          <option value="Botmaker">Botmaker</option>
          <option value="ThinkChat">ThinkChat</option>
          <option value="Manual">Manual</option>
        </select>
        <button onClick={search} disabled={loading} className="bg-neon-lime text-pitch-black font-[590] text-sm rounded-md px-6 py-3 hover:opacity-90 disabled:opacity-50">
          {loading ? "..." : "Buscar"}
        </button>
      </div>

      {error && <p className="text-warning-red text-sm">{error}</p>}

      {data && (() => {
        // Cross-check: which EPEM phones also have DW matches?
        const dwPhones = new Set(data.dw_matches.map((m: any) => m.phone));
        const cruceCompleto = data.dw_matches.length > 0 && data.epem_historial.length > 0;
        return (
        <div className="space-y-4 max-w-4xl">
          {cruceCompleto && (
            <div className="bg-emerald/10 border border-emerald/30 rounded-md p-3 text-xs text-emerald">
              ✓ CRUCE COMPLETO — Lead encontrado en DW (PostgreSQL) y EPEM (MySQL). Cobertura total.
            </div>
          )}
          {data.dw_matches.length === 0 && data.epem_historial.length > 0 && (
            <div className="bg-amber-300/10 border border-amber-300/30 rounded-md p-3 text-xs text-amber-300">
              ⚠ Solo en EPEM — este lead no esta en el DW. Posible gap de ETL.
            </div>
          )}
          {data.dw_matches.length > 0 && data.epem_historial.length === 0 && (
            <div className="bg-aether-blue/10 border border-aether-blue/30 rounded-md p-3 text-xs text-aether-blue">
              ℹ Solo en DW — lead no encontrado en EPEM (posible lead nuevo).
            </div>
          )}

          {data.dw_matches.length > 0 && (
            <div className="bg-graphite rounded-md p-5 border-l-2 border-aether-blue">
              <h2 className="text-xs font-[510] text-storm-cloud uppercase tracking-wider mb-2">CRM (DW) Match — {data.dw_matches.length}</h2>
              {data.dw_matches.map((m: any, i: number) => {
                const fuenteColor = FUENTE_COLORS[m.fuente_origen] || FUENTE_COLORS.Manual;
                return (
                  <div key={i} className="text-sm text-light-steel flex items-center gap-3 mb-1">
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-[510] ${FUENTE_COLORS.DW}`}>DW</span>
                    <span className="text-porcelain font-[510]">ID {m.id}</span>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-[510] ${fuenteColor}`}>{m.fuente_origen}</span>
                    <span>Status {m.status}</span>
                    <span>UN {UN_MAP[m.enterprise_id] || m.enterprise_id}</span>
                    {m.es_venta_dw && <span className="text-[10px] px-2 py-0.5 rounded-full font-[510] bg-emerald/20 text-emerald">VENTA</span>}
                  </div>
                );
              })}
            </div>
          )}

          {data.epem_historial.map((h) => {
            const isInDW = dwPhones.has(h.phone);
            return (
            <div key={h.id} className="bg-graphite rounded-md p-5 border-l-2 border-neon-lime">
              <div className="grid grid-cols-3 gap-5">
                <div className="col-span-2">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-[510] ${FUENTE_COLORS.EPEM}`}>EPEM</span>
                    <h3 className="text-base font-[590] text-porcelain">{h.fullname}</h3>
                    <span className="text-[10px] text-fog-grey">ID {h.id}</span>
                    {h.lead_source && <span className={`text-[10px] px-2 py-0.5 rounded-full font-[510] ${h.lead_source.toLowerCase().includes('think') ? FUENTE_COLORS.ThinkChat : h.lead_source.toLowerCase().includes('bot') ? FUENTE_COLORS.Botmaker : FUENTE_COLORS.Manual}`}>{h.lead_source}</span>}
                    {isInDW && <span className="text-[10px] px-2 py-0.5 rounded-full font-[510] bg-emerald/20 text-emerald">DW MATCH</span>}
                  </div>
                  <div className="text-xs text-storm-cloud mb-3">{h.phone}</div>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
                    <div><span className="text-fog-grey">UN: </span><span className="text-light-steel">{UN_MAP[h.enterprise_id] || h.enterprise_id}</span></div>
                    <div><span className="text-fog-grey">Vendedor: </span><span className="text-light-steel">{h.seller || "—"}</span></div>
                    {h.closer && <div><span className="text-fog-grey">Cerrador: </span><span className="text-deep-violet">{h.closer}</span></div>}
                    <div><span className="text-fog-grey">Status: </span><span className={h.status === 15 ? "text-emerald" : h.status === 30 ? "text-warning-red" : "text-deep-violet"}>{STATUS_MAP[h.status] || `S-${h.status}`}</span></div>
                    {h.lead_source && <div><span className="text-fog-grey">Fuente: </span><span className="text-light-steel">{h.lead_source}</span></div>}
                    {h.contract_id && <div><span className="text-fog-grey">Contrato: </span><span className="text-aether-blue">#{h.contract_id}</span></div>}
                    {h.form_id && <div><span className="text-fog-grey">Form: </span><span className="text-light-steel">#{h.form_id}</span></div>}
                    {h.ad_id && <div><span className="text-fog-grey">Ad ID: </span><span className="text-light-steel">{h.ad_id}</span></div>}
                    {h.deadline && h.deadline !== "None" && <div><span className="text-fog-grey">Deadline: </span><span className="text-amber-300">{fmt(h.deadline)}</span></div>}
                    {h.rejected_at && h.rejected_at !== "None" && <div><span className="text-fog-grey">Rechazado: </span><span className="text-warning-red">{fmt(h.rejected_at)}</span></div>}
                    {h.observation && <div className="col-span-2"><span className="text-fog-grey">Obs: </span><span className="text-light-steel">{h.observation}</span></div>}
                  </div>
                </div>
                <div>
                  <p className="text-[10px] text-fog-grey uppercase tracking-wider mb-2">Timeline</p>
                  <Timeline h={h} />
                </div>
              </div>
            </div>
            );
          })}

          {data.epem_historial.length === 0 && !data.epem_error && (
            <p className="text-storm-cloud text-sm">Sin resultados en EPEM.</p>
          )}
          {data.epem_error && <p className="text-warning-red text-sm">{data.epem_error}</p>}
        </div>
        );
      })()}
    </div>
  );
}

