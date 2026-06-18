"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";

interface LeadRow {
  id: string; fullname: string; phone: string;
  enterprise_id: number; un_nombre: string;
  fuente: string; status: number; status_label: string;
  vendedor_nombre: string | null; vendedor_id: number | null;
  first_seen_at: string | null; ad_id: string | null;
}

interface LeadsStats {
  total: number; botmaker: number; thinkchat: number; manual: number;
  por_un: Record<string, number>;
}

interface LeadsResponse {
  stats: LeadsStats;
  leads: LeadRow[];
  pagination: { page: number; limit: number; total: number; pages: number };
  filtros: { dias: number; fuente: string | null; enterprise_id: number | null; status: number | null };
}

const UN_MAP: Record<number, string> = { 1: "Odontologia", 2: "Med. Prepaga", 4: "Emergencias", 5: "Med. Estetica" };
const STATUS_COLOR: Record<number, string> = {
  1: "text-storm-cloud", 5: "text-cyan-spark", 10: "text-aether-blue", 15: "text-emerald", 30: "text-warning-red"
};
const FUENTE_COLORS: Record<string, string> = {
  ThinkChat: "bg-emerald/20 text-emerald",
  "ThinkChat->Venta": "bg-emerald/20 text-emerald",
  Botmaker: "bg-aether-blue/20 text-aether-blue",
  Manual: "bg-fog-grey/20 text-light-steel",
};

function fmt(d: string | null | undefined): string {
  if (!d) return "\u2014";
  return d.replace("T", " ").slice(0, 16);
}

export default function LeadsPage() {
  const router = useRouter();
  const [data, setData] = useState<LeadsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [dias, setDias] = useState(1);
  const [fuente, setFuente] = useState("");
  const [enterpriseId, setEnterpriseId] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);

  const fetchLeads = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const token = localStorage.getItem("token");
      const params = new URLSearchParams();
      params.set("dias", String(dias));
      params.set("limit", "50");
      params.set("page", String(page));
      if (fuente) params.set("fuente", fuente);
      if (enterpriseId) params.set("enterprise_id", enterpriseId);
      if (status) params.set("status", status);

      const res = await fetch("http://localhost:8000/api/dashboard/leads?" + params, {
        headers: { Authorization: "Bearer " + token },
      });
      if (!res.ok) throw new Error("Error al cargar leads");
      setData(await res.json());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [dias, fuente, enterpriseId, status, page]);

  useEffect(() => { fetchLeads(); }, [fetchLeads]);

  const goToLead = (id: string) => router.push("/dashboard/lead/" + id);
  const goToSeller = (id: number) => router.push("/dashboard/seller/" + id);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-[590] text-porcelain tracking-[-0.22px]">Leads</h1>
        <p className="text-storm-cloud text-sm mt-1">Leads entrantes con desglose por fuente y unidad de negocio</p>
      </div>

      {error && <p className="text-warning-red text-sm">{error}</p>}

      {/* KPI Cards */}
      {data?.stats && (
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-graphite rounded-md p-4 border-l-2 border-neon-lime">
            <p className="text-[10px] text-fog-grey uppercase tracking-wider">Total Leads</p>
            <p className="text-2xl font-[590] text-porcelain mt-1">{data.stats.total}</p>
            <p className="text-[11px] text-storm-cloud mt-0.5">{dias === 1 ? "hoy" : dias + "d"}</p>
          </div>
          <div className="bg-graphite rounded-md p-4 border-l-2 border-aether-blue">
            <p className="text-[10px] text-fog-grey uppercase tracking-wider">Botmaker</p>
            <p className="text-2xl font-[590] text-porcelain mt-1">{data.stats.botmaker}</p>
            <p className="text-[11px] text-storm-cloud mt-0.5">{data.stats.total > 0 ? Math.round(data.stats.botmaker / data.stats.total * 100) : 0}%</p>
          </div>
          <div className="bg-graphite rounded-md p-4 border-l-2 border-emerald">
            <p className="text-[10px] text-fog-grey uppercase tracking-wider">ThinkChat</p>
            <p className="text-2xl font-[590] text-porcelain mt-1">{data.stats.thinkchat}</p>
            <p className="text-[11px] text-storm-cloud mt-0.5">{data.stats.total > 0 ? Math.round(data.stats.thinkchat / data.stats.total * 100) : 0}%</p>
          </div>
        </div>
      )}

      {/* Filtros */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex gap-1.5">
          {[1, 7, 30].map((d) => (
            <button
              key={d}
              onClick={() => { setDias(d); setPage(1); }}
              className={"text-xs px-3 py-1.5 rounded-full font-[510] transition-colors " + (
                dias === d ? "bg-neon-lime text-pitch-black" : "bg-charcoal-grey text-storm-cloud hover:text-porcelain"
              )}
            >
              {d === 1 ? "Hoy" : d === 7 ? "7d" : "30d"}
            </button>
          ))}
        </div>

        <select value={fuente} onChange={(e) => { setFuente(e.target.value); setPage(1); }}
          className="bg-pitch-black border border-charcoal-grey rounded-md px-3 py-2 text-porcelain text-sm focus:border-neon-lime focus:outline-none">
          <option value="">Todas fuentes</option>
          <option value="Botmaker">Botmaker</option>
          <option value="ThinkChat">ThinkChat</option>
          <option value="Manual">Manual</option>
        </select>

        <select value={enterpriseId} onChange={(e) => { setEnterpriseId(e.target.value); setPage(1); }}
          className="bg-pitch-black border border-charcoal-grey rounded-md px-3 py-2 text-porcelain text-sm focus:border-neon-lime focus:outline-none">
          <option value="">Todas UN</option>
          {Object.entries(UN_MAP).map(([id, name]) => (
            <option key={id} value={id}>{name}</option>
          ))}
        </select>

        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          className="bg-pitch-black border border-charcoal-grey rounded-md px-3 py-2 text-porcelain text-sm focus:border-neon-lime focus:outline-none">
          <option value="">Todos status</option>
          <option value="1">Nuevo</option>
          <option value="5">Contactado</option>
          <option value="10">Gestionado</option>
          <option value="15">Vendido</option>
          <option value="30">Descartado</option>
        </select>

        {data?.pagination && (
          <span className="text-xs text-fog-grey ml-auto">
            {data.pagination.total} leads | Pag {data.pagination.page}/{data.pagination.pages}
          </span>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div className="bg-graphite rounded-md p-8 animate-pulse">
          <div className="h-4 bg-charcoal-grey rounded w-64 mb-3" />
          <div className="h-3 bg-charcoal-grey rounded w-full mb-2" />
          <div className="h-3 bg-charcoal-grey rounded w-full mb-2" />
          <div className="h-3 bg-charcoal-grey rounded w-3/4" />
        </div>
      )}

      {/* Tabla */}
      {!loading && data && data.leads.length > 0 && (
        <div className="bg-graphite rounded-md overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-charcoal-grey text-fog-grey text-[10px] uppercase tracking-wider">
                <th className="text-left px-4 py-2">Lead</th>
                <th className="text-left px-4 py-2">Telefono</th>
                <th className="text-left px-4 py-2">Fuente</th>
                <th className="text-left px-4 py-2">UN</th>
                <th className="text-left px-4 py-2">Status</th>
                <th className="text-left px-4 py-2">Vendedor</th>
                <th className="text-left px-4 py-2">Meta ID</th>
                <th className="text-left px-4 py-2">Fecha</th>
              </tr>
            </thead>
            <tbody>
              {data.leads.map((l) => (
                <tr
                  key={l.id}
                  className="border-b border-charcoal-grey/50 hover:bg-deep-slate/30 cursor-pointer transition-colors"
                  onClick={() => goToLead(l.id)}
                >
                  <td className="px-4 py-2.5 text-porcelain font-[510]">{l.fullname}</td>
                  <td className="px-4 py-2.5 text-fog-grey">{l.phone}</td>
                  <td className="px-4 py-2.5">
                    <span className={"text-[10px] px-2 py-0.5 rounded-full font-[510] " + (FUENTE_COLORS[l.fuente] || FUENTE_COLORS.Manual)}>{l.fuente}</span>
                  </td>
                  <td className="px-4 py-2.5 text-fog-grey">{l.un_nombre}</td>
                  <td className="px-4 py-2.5">
                    <span className={"font-[510] " + (STATUS_COLOR[l.status] || "text-storm-cloud")}>{l.status_label}</span>
                  </td>
                  <td className="px-4 py-2.5">
                    {l.vendedor_nombre ? (
                      <span className="text-light-steel cursor-pointer hover:text-neon-lime" onClick={(e) => { e.stopPropagation(); goToSeller(l.vendedor_id!); }}>{l.vendedor_nombre}</span>
                    ) : (
                      <span className="text-fog-grey">{"\u2014"}</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-fog-grey font-mono text-[10px]">{l.ad_id ? l.ad_id.slice(-12) : "\u2014"}</td>
                  <td className="px-4 py-2.5 text-fog-grey">{fmt(l.first_seen_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Empty */}
      {!loading && data && data.leads.length === 0 && (
        <div className="bg-graphite rounded-md p-8 text-center">
          <p className="text-storm-cloud text-sm">Sin leads con los filtros actuales.</p>
        </div>
      )}

      {/* Pagination */}
      {!loading && data && data.pagination.pages > 1 && (
        <div className="flex justify-center gap-2">
          {Array.from({ length: data.pagination.pages }, (_, i) => i + 1).map((p) => (
            <button
              key={p}
              onClick={() => setPage(p)}
              className={"text-xs px-3 py-1.5 rounded-md font-[510] transition-colors " + (
                p === page ? "bg-neon-lime text-pitch-black" : "bg-charcoal-grey text-storm-cloud hover:text-porcelain"
              )}
            >
              {p}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}