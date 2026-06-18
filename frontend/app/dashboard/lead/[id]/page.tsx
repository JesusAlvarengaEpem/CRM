"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

interface LeadDetail {
  id: string; phone: string; fullname: string; email: string | null;
  enterprise_id: number; un_nombre: string; branch_id: number | null;
  seller_id: number | null; vendedor_nombre: string | null;
  closer_id: number | null; cerrador_nombre: string | null;
  contract_id: number | null; monto?: number | null;
  status: number; status_label: string;
  observation: string | null;
  fuente: string; es_venta: number;
  es_pauta: number; es_botmaker: number; es_thinkchat: number;
  first_seen_at: string | null; last_updated_at: string | null;
  epem_opportunity_id: number;
  bm_customer_id: string | null;
  ad_id: string | null;
}

interface Tracking {
  timestamp: string | null;
  from_status: number | null; from_status_label: string | null;
  to_status: number | null; to_status_label: string | null;
  seller_id: number | null; vendedor_nombre: string | null;
  source: string | null;
}

interface LeadResponse {
  lead: LeadDetail;
  trackings: Tracking[];
}

const STATUS_COLOR: Record<number, string> = {
  1: "text-storm-cloud", 5: "text-cyan-spark", 10: "text-aether-blue", 15: "text-emerald", 30: "text-warning-red"
};
const FUENTE_COLORS: Record<string, string> = {
  ThinkChat: "bg-emerald/20 text-emerald",
  Botmaker: "bg-aether-blue/20 text-aether-blue",
  Manual: "bg-fog-grey/20 text-light-steel",
};
const TIPO_DOT: Record<string, string> = {
  sold: "bg-emerald", reject: "bg-warning-red", closer: "bg-deep-violet",
  reassigned: "bg-amber-300", attended: "bg-aether-blue", default: "bg-cyan-spark"
};

function fmt(d: string | null | undefined): string {
  if (!d) return "\u2014";
  return d.replace("T", " ").slice(0, 16);
}

function fmtMonto(m: number | null | undefined): string {
  if (m == null || m === 0) return "\u2014";
  if (m >= 1_000_000) return "Gs " + (m / 1_000_000).toFixed(1) + "M";
  return "Gs " + m.toLocaleString("es-PY");
}

function inferTrackingType(t: Tracking): string {
  if (t.to_status === 15) return "sold";
  if (t.to_status === 30) return "reject";
  if (t.source && t.source.includes("closer")) return "closer";
  if (t.source && t.source.includes("reassign")) return "reassigned";
  if (t.to_status === 5) return "attended";
  return "default";
}

export default function LeadDetailPage() {
  const params = useParams();
  const router = useRouter();
  const leadId = params.id as string;

  const [data, setData] = useState<LeadResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!leadId) return;
    const token = localStorage.getItem("token");
    if (!token) { router.push("/"); return; }

    fetch("http://localhost:8000/api/dashboard/lead/" + leadId, {
      headers: { Authorization: "Bearer " + token },
    })
      .then((res) => {
        if (!res.ok) throw new Error("Lead no encontrado");
        return res.json();
      })
      .then((d: LeadResponse) => setData(d))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [leadId]);

  if (loading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="h-6 bg-charcoal-grey rounded w-48" />
        <div className="h-4 bg-charcoal-grey rounded w-32" />
        <div className="bg-graphite rounded-md p-6">
          <div className="h-4 bg-charcoal-grey rounded w-64 mb-3" />
          <div className="h-3 bg-charcoal-grey rounded w-40" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <button onClick={() => router.back()} className="text-storm-cloud hover:text-porcelain text-sm transition-colors">
          {"\u2190"} Volver
        </button>
        <div className="bg-warning-red/10 border border-warning-red/30 rounded-md p-4 text-warning-red text-sm">
          {error}
        </div>
      </div>
    );
  }

  if (!data) return null;
  const { lead, trackings } = data;

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Back button */}
      <button onClick={() => router.back()} className="text-storm-cloud hover:text-porcelain text-sm transition-colors">
        {"\u2190"} Volver a Actividad
      </button>

      {/* Lead header */}
      <div className="bg-graphite rounded-md p-6 border-l-2 border-neon-lime">
        <div className="flex items-center gap-2 flex-wrap mb-2">
          <span className={"text-[10px] px-2 py-0.5 rounded-full font-[510] " + (FUENTE_COLORS[lead.fuente] || FUENTE_COLORS.Manual)}>
            {lead.fuente}
          </span>
          <span className="text-[10px] text-fog-grey">{lead.un_nombre}</span>
          <span className={"text-xs font-[510] " + (STATUS_COLOR[lead.status] || "text-storm-cloud")}>
            {lead.status_label}
          </span>
          {lead.es_venta === 1 && (
            <span className="text-[10px] px-2 py-0.5 rounded-full font-[510] bg-emerald/20 text-emerald">VENTA</span>
          )}
          {lead.es_pauta === 1 && (
            <span className="text-[10px] px-2 py-0.5 rounded-full font-[510] bg-neon-lime/20 text-neon-lime">PAUTA</span>
          )}
          {lead.es_botmaker === 1 && (
            <span className="text-[10px] px-2 py-0.5 rounded-full font-[510] bg-aether-blue/20 text-aether-blue">BOTMAKER</span>
          )}
          {lead.es_thinkchat === 1 && (
            <span className="text-[10px] px-2 py-0.5 rounded-full font-[510] bg-emerald/20 text-emerald">THINKCHAT</span>
          )}
        </div>

        <h1 className="text-xl font-[590] text-porcelain">{lead.fullname}</h1>
        <p className="text-sm text-fog-grey mt-0.5">{lead.phone}</p>
        {lead.email && <p className="text-xs text-storm-cloud">{lead.email}</p>}

        {/* IDs */}
        <div className="flex items-center gap-2 mt-2 flex-wrap">
          <span className="text-[10px] px-2 py-0.5 rounded-full font-[510] bg-deep-slate text-fog-grey">
            DW: {lead.id.slice(0, 8)}...
          </span>
          <span className="text-[10px] px-2 py-0.5 rounded-full font-[510] bg-deep-slate text-cyan-spark">
            EPEM #{lead.epem_opportunity_id}
          </span>
          {lead.bm_customer_id && (
            <span className="text-[10px] px-2 py-0.5 rounded-full font-[510] bg-deep-slate text-aether-blue">
              BM: {lead.bm_customer_id}
            </span>
          )}
          {lead.ad_id && (
            <span className="text-[10px] px-2 py-0.5 rounded-full font-[510] bg-deep-slate text-neon-lime">
              Meta ID: {lead.ad_id}
            </span>
          )}
        </div>

        {/* Metadata grid */}
        <div className="grid grid-cols-2 gap-x-6 gap-y-2 mt-4 text-xs">
          <div><span className="text-fog-grey">Vendedor: </span><span className="text-light-steel">{lead.vendedor_nombre || "\u2014"}</span></div>
          <div><span className="text-fog-grey">Cerrador: </span><span className="text-deep-violet">{lead.cerrador_nombre || "\u2014"}</span></div>
          <div><span className="text-fog-grey">Ingreso: </span><span className="text-light-steel">{fmt(lead.first_seen_at)}</span></div>
          <div><span className="text-fog-grey">{lead.es_venta === 1 ? "Vendido: " : "Ultima act: "}</span><span className={lead.es_venta === 1 ? "text-emerald font-[510]" : "text-light-steel"}>{fmt(lead.last_updated_at)}</span></div>
          {lead.contract_id && (
            <div><span className="text-fog-grey">Contrato: </span>
              <a href={"https://sistema.grupoepem.com.py/contracts/" + lead.contract_id} target="_blank" rel="noopener noreferrer"
                 className="text-aether-blue font-[510] hover:text-neon-lime transition-colors cursor-pointer"
                 onClick={(e) => e.stopPropagation()}>
                #{lead.contract_id} ↗
              </a>
            </div>
          )}
          {lead.monto != null && (
            <div><span className="text-fog-grey">Monto: </span><span className="text-emerald font-[590]">{fmtMonto(lead.monto)}</span></div>
          )}
          <div><span className="text-fog-grey">EPEM ID: </span><span className="text-light-steel">{lead.epem_opportunity_id}</span></div>
        </div>

        {lead.observation && (
          <div className="mt-3 pt-3 border-t border-charcoal-grey">
            <p className="text-[10px] text-fog-grey uppercase tracking-wider mb-1">Observacion</p>
            <p className="text-xs text-light-steel">{lead.observation}</p>
          </div>
        )}
      </div>

      {/* Timeline */}
      <div>
        <h2 className="text-sm font-[510] text-storm-cloud uppercase tracking-wider mb-4">
          Timeline ({trackings.length} eventos)
        </h2>

        {trackings.length === 0 ? (
          <p className="text-storm-cloud text-sm">Sin historial de tracking.</p>
        ) : (
          <div className="relative pl-8">
            <div className="absolute left-[15px] top-2 bottom-2 w-px bg-charcoal-grey" />
            <div className="space-y-1">
              {trackings.map((t, i) => {
                const tipo = inferTrackingType(t);
                return (
                  <div key={i} className="relative pb-3 last:pb-0">
                    <div className={"absolute left-[-17px] top-1.5 w-2.5 h-2.5 rounded-full " + (TIPO_DOT[tipo] || TIPO_DOT.default) + " ring-2 ring-pitch-black"} />
                    <div className="text-[11px] text-fog-grey">{fmt(t.timestamp)}</div>
                    <div className="flex items-center gap-2 text-xs">
                      {t.from_status_label && (
                        <>
                          <span className="text-fog-grey">{t.from_status_label}</span>
                          <span className="text-storm-cloud">{"\u2192"}</span>
                        </>
                      )}
                      <span className={"font-[510] " + (STATUS_COLOR[t.to_status || 0] || "text-porcelain")}>
                        {t.to_status_label || "Contacto"}
                      </span>
                    </div>
                    {t.vendedor_nombre && (
                      <div className="text-[10px] text-fog-grey mt-0.5">{t.vendedor_nombre}</div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}