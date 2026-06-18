"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

interface VendedorStats {
  leads: number; gestionados: number; ventas: number;
  nuevos: number; perdidos: number; conversion: number;
}

interface LeadMini {
  id: string; fullname: string; phone: string;
  enterprise_id: number; un_nombre: string;
  fuente: string; status: number; status_label: string;
  first_seen_at: string | null;
}

interface GestionMini {
  timestamp: string | null; to_status: number; to_status_label: string | null;
  lead_id: string; fullname: string; phone: string;
}

interface VendedorResponse {
  seller_id: number; nombre: string;
  supervisor_id: number | null; supervisor_nombre: string | null;
  stats: VendedorStats;
  leads_recientes: LeadMini[];
  gestiones: GestionMini[];
}

const STATUS_COLOR: Record<number, string> = {
  1: "text-storm-cloud", 5: "text-cyan-spark", 10: "text-aether-blue", 15: "text-emerald", 30: "text-warning-red"
};
const FUENTE_COLORS: Record<string, string> = {
  ThinkChat: "bg-emerald/20 text-emerald",
  Botmaker: "bg-aether-blue/20 text-aether-blue",
  Manual: "bg-fog-grey/20 text-light-steel",
};

function fmt(d: string | null | undefined): string {
  if (!d) return "\u2014";
  return d.replace("T", " ").slice(0, 16);
}

export default function SellerDetailPage() {
  const params = useParams();
  const router = useRouter();
  const sellerId = params.id as string;

  const [data, setData] = useState<VendedorResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!sellerId) return;
    const token = localStorage.getItem("token");
    if (!token) { router.push("/"); return; }

    fetch("http://localhost:8000/api/dashboard/vendedor/" + sellerId, {
      headers: { Authorization: "Bearer " + token },
    })
      .then((res) => {
        if (!res.ok) throw new Error("Vendedor no encontrado");
        return res.json();
      })
      .then((d: VendedorResponse) => setData(d))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [sellerId]);

  if (loading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="h-6 bg-charcoal-grey rounded w-48" />
        <div className="grid grid-cols-4 gap-4">
          {[1,2,3,4].map((i) => (
            <div key={i} className="bg-graphite rounded-md p-4"><div className="h-3 bg-charcoal-grey rounded w-16 mb-2" /><div className="h-6 bg-charcoal-grey rounded w-12" /></div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <button onClick={() => router.back()} className="text-storm-cloud hover:text-porcelain text-sm">{"\u2190"} Volver</button>
        <div className="bg-warning-red/10 border border-warning-red/30 rounded-md p-4 text-warning-red text-sm">{error}</div>
      </div>
    );
  }

  if (!data) return null;
  const { nombre, supervisor_nombre, stats, leads_recientes, gestiones } = data;

  return (
    <div className="space-y-6 max-w-4xl">
      <button onClick={() => router.back()} className="text-storm-cloud hover:text-porcelain text-sm transition-colors">
        {"\u2190"} Volver
      </button>

      {/* Header */}
      <div className="bg-graphite rounded-md p-6 border-l-2 border-deep-violet">
        <h1 className="text-xl font-[590] text-porcelain">{nombre}</h1>
        {supervisor_nombre && (
          <p className="text-sm text-storm-cloud mt-1">
            <span className="text-fog-grey">Supervisor: </span>
            <span className="text-light-steel">{supervisor_nombre}</span>
          </p>
        )}
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-5 gap-4">
        <div className="bg-graphite rounded-md p-4 border-l-2 border-aether-blue">
          <p className="text-[10px] text-fog-grey uppercase tracking-wider">Leads 30d</p>
          <p className="text-2xl font-[590] text-porcelain mt-1">{stats.leads}</p>
        </div>
        <div className="bg-graphite rounded-md p-4 border-l-2 border-cyan-spark">
          <p className="text-[10px] text-fog-grey uppercase tracking-wider">Gestionados</p>
          <p className="text-2xl font-[590] text-porcelain mt-1">{stats.gestionados}</p>
        </div>
        <div className="bg-graphite rounded-md p-4 border-l-2 border-emerald">
          <p className="text-[10px] text-fog-grey uppercase tracking-wider">Ventas</p>
          <p className="text-2xl font-[590] text-porcelain mt-1">{stats.ventas}</p>
        </div>
        <div className="bg-graphite rounded-md p-4 border-l-2 border-deep-violet">
          <p className="text-[10px] text-fog-grey uppercase tracking-wider">Conversion</p>
          <p className="text-2xl font-[590] text-porcelain mt-1">{stats.conversion}%</p>
        </div>
        <div className="bg-graphite rounded-md p-4 border-l-2 border-warning-red">
          <p className="text-[10px] text-fog-grey uppercase tracking-wider">Perdidos</p>
          <p className="text-2xl font-[590] text-porcelain mt-1">{stats.perdidos}</p>
        </div>
      </div>

      {/* Leads recientes */}
      <div>
        <h2 className="text-sm font-[510] text-storm-cloud uppercase tracking-wider mb-3">
          Leads Recientes ({leads_recientes.length})
        </h2>
        <div className="bg-graphite rounded-md overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-charcoal-grey text-fog-grey text-[10px] uppercase tracking-wider">
                <th className="text-left px-4 py-2">Lead</th>
                <th className="text-left px-4 py-2">Telefono</th>
                <th className="text-left px-4 py-2">Fuente</th>
                <th className="text-left px-4 py-2">UN</th>
                <th className="text-left px-4 py-2">Status</th>
                <th className="text-left px-4 py-2">Fecha</th>
              </tr>
            </thead>
            <tbody>
              {leads_recientes.map((l) => (
                <tr
                  key={l.id}
                  className="border-b border-charcoal-grey/50 hover:bg-deep-slate/30 cursor-pointer transition-colors"
                  onClick={() => router.push("/dashboard/lead/" + l.id)}
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
                  <td className="px-4 py-2.5 text-fog-grey">{fmt(l.first_seen_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Gestiones recientes */}
      <div>
        <h2 className="text-sm font-[510] text-storm-cloud uppercase tracking-wider mb-3">
          Ultimas Gestiones ({gestiones.length})
        </h2>
        <div className="relative pl-8">
          <div className="absolute left-[15px] top-2 bottom-2 w-px bg-charcoal-grey" />
          <div className="space-y-1">
            {gestiones.map((g, i) => (
              <div key={i} className="relative pb-3 last:pb-0">
                <div className="absolute left-[-17px] top-1.5 w-2.5 h-2.5 rounded-full bg-cyan-spark ring-2 ring-pitch-black" />
                <div className="text-[11px] text-fog-grey">{fmt(g.timestamp)}</div>
                <div className="flex items-center gap-2 text-xs">
                  <span
                    className="text-porcelain font-[510] cursor-pointer hover:text-neon-lime"
                    onClick={(e) => { e.stopPropagation(); router.push("/dashboard/lead/" + g.lead_id); }}
                  >
                    {g.fullname}
                  </span>
                  <span className="text-fog-grey">{g.phone}</span>
                  <span className={"font-[510] " + (STATUS_COLOR[g.to_status] || "text-storm-cloud")}>
                    {g.to_status_label || "Contacto"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}