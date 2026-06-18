"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";

interface Evento {
  tipo: "lead_nuevo" | "gestion" | "venta";
  timestamp: string;
  relativo: string;
  lead_id: string;
  fullname: string;
  phone: string;
  enterprise_id: number;
  un_nombre: string;
  fuente: string;
  vendedor_nombre: string | null;
  vendedor_id: number | null;
  cerrador_nombre: string | null;
  cerrador_id: number | null;
  status: number;
  status_label: string;
  from_status?: number;
  from_status_label?: string;
  contract_id?: number;
  monto?: number | null;
}

interface ActividadResponse {
  eventos: Evento[];
  total: number;
  filtros: { enterprise_id: number | null; fuente: string | null; tipo: string | null; limit: number };
}

interface StatsResponse {
  hoy: { leads: number; gestiones: number; ventas: number; monto: number };
  semana: { leads: number; gestiones: number; ventas: number };
}

const UN_MAP: Record<number, string> = { 1: "Odontologia", 2: "Med. Prepaga", 4: "Emergencias", 5: "Med. Estetica" };
const TIPO_ICON: Record<string, string> = { lead_nuevo: "\u{1F195}", gestion: "\u{1F504}", venta: "\u{1F4B0}" };
const TIPO_LABEL: Record<string, string> = { lead_nuevo: "Lead Nuevo", gestion: "Gestion", venta: "Venta" };
const TIPO_COLOR: Record<string, string> = { lead_nuevo: "border-aether-blue", gestion: "border-cyan-spark", venta: "border-emerald" };
const TIPO_DOT: Record<string, string> = { lead_nuevo: "bg-aether-blue", gestion: "bg-cyan-spark", venta: "bg-emerald" };
const FUENTE_COLORS: Record<string, string> = {
  ThinkChat: "bg-emerald/20 text-emerald",
  Botmaker: "bg-aether-blue/20 text-aether-blue",
  Manual: "bg-fog-grey/20 text-light-steel",
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

export default function ActividadPage() {
  const router = useRouter();
  const [eventos, setEventos] = useState<Evento[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);
  const [stats, setStats] = useState<StatsResponse | null>(null);

  const [tipo, setTipo] = useState<string>("");
  const [enterpriseId, setEnterpriseId] = useState<string>("");
  const [fuente, setFuente] = useState<string>("");

  const fetchStats = useCallback(async () => {
    try {
      const token = localStorage.getItem("token");
      const params = new URLSearchParams();
      if (enterpriseId) params.set("enterprise_id", enterpriseId);
      if (fuente) params.set("fuente", fuente);
      const res = await fetch("http://localhost:8000/api/dashboard/actividad/stats?" + params, {
        headers: { Authorization: "Bearer " + token },
      });
      if (res.ok) setStats(await res.json());
    } catch {}
  }, [enterpriseId, fuente]);

  const fetchActividad = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const token = localStorage.getItem("token");
      const params = new URLSearchParams();
      params.set("limit", "200");
      if (tipo) params.set("tipo", tipo);
      if (enterpriseId) params.set("enterprise_id", enterpriseId);
      if (fuente) params.set("fuente", fuente);

      const res = await fetch("http://localhost:8000/api/dashboard/actividad?" + params, {
        headers: { Authorization: "Bearer " + token },
      });
      if (!res.ok) throw new Error("Error al cargar actividad");
      const data: ActividadResponse = await res.json();
      setEventos(data.eventos);
      setTotal(data.total);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [tipo, enterpriseId, fuente]);

  useEffect(() => { fetchActividad(); fetchStats(); }, [fetchActividad, fetchStats]);

  const syncTodo = async () => {
    setSyncing(true); setSyncResult(null);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch("http://localhost:8000/api/etl/sync/todo", {
        method: "POST",
        headers: { Authorization: "Bearer " + token },
      });
      const data = await res.json();
      if (data.status === "ok") {
        setSyncResult("\u2705 " + data.message);
        fetchActividad();
        fetchStats();
        setSyncing(false);
        // Auto-refresh para capturar ThinkChat (background, ~60s)
        if (data.thinkchat === "pending") {
          setTimeout(() => {
            setSyncResult("\u23F3 ThinkChat procesando... refrescando en 5s");
            fetchActividad(); fetchStats();
          }, 5000);
          setTimeout(() => {
            setSyncResult("\u2705 Sync completo — leads, gestiones y ThinkChat actualizados");
            fetchActividad(); fetchStats();
          }, 10000);
        }
      } else {
        setSyncResult("\u26A0 Error en sync");
        setSyncing(false);
      }
    } catch (e: any) {
      setSyncResult("\u274C " + e.message);
      setSyncing(false);
    }
  };

  const goToLead = (leadId: string) => {
    router.push("/dashboard/lead/" + leadId);
  };

  const goToSeller = (sellerId: number) => {
    router.push("/dashboard/seller/" + sellerId);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-[590] text-porcelain tracking-[-0.22px]">Actividad</h1>
          <p className="text-storm-cloud text-sm mt-1">Ultimos movimientos \u2014 leads nuevos, gestiones y ventas</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => { fetchActividad(); fetchStats(); }}
            disabled={loading}
            className="bg-charcoal-grey text-light-steel text-sm rounded-md px-4 py-2.5 hover:bg-deep-slate hover:text-porcelain transition-colors disabled:opacity-50"
          >
            {loading ? "\u23F3" : "\u{1F504}"} Actualizar
          </button>
          <button
            onClick={syncTodo}
            disabled={syncing}
            className="bg-neon-lime text-pitch-black text-sm font-[590] rounded-md px-4 py-2.5 hover:opacity-90 transition-colors disabled:opacity-50"
          >
            {syncing ? "\u23F3 Sincronizando..." : "\u26A1 Sync Todo"}
          </button>
        </div>
      </div>

      {syncResult && (
        <div className={"text-sm rounded-md p-3 " + (syncResult.startsWith("\u2705") ? "bg-emerald/10 border border-emerald/30 text-emerald" : syncResult.startsWith("\u26A0") ? "bg-amber-300/10 border border-amber-300/30 text-amber-300" : "bg-warning-red/10 border border-warning-red/30 text-warning-red")}>
          {syncResult}
        </div>
      )}

      {stats && (
        <div className="grid grid-cols-4 gap-4">
          <div className="bg-graphite rounded-md p-4 border-l-2 border-aether-blue">
            <p className="text-[10px] text-fog-grey uppercase tracking-wider">Leads Hoy</p>
            <p className="text-2xl font-[590] text-porcelain mt-1">{stats.hoy.leads}</p>
            <p className="text-[11px] text-storm-cloud mt-0.5">{stats.semana.leads} esta semana</p>
          </div>
          <div className="bg-graphite rounded-md p-4 border-l-2 border-cyan-spark">
            <p className="text-[10px] text-fog-grey uppercase tracking-wider">Gestiones Hoy</p>
            <p className="text-2xl font-[590] text-porcelain mt-1">{stats.hoy.gestiones}</p>
            <p className="text-[11px] text-storm-cloud mt-0.5">{stats.semana.gestiones} esta semana</p>
          </div>
          <div className="bg-graphite rounded-md p-4 border-l-2 border-emerald">
            <p className="text-[10px] text-fog-grey uppercase tracking-wider">Ventas Hoy</p>
            <p className="text-2xl font-[590] text-porcelain mt-1">{stats.hoy.ventas}</p>
            <p className="text-[11px] text-storm-cloud mt-0.5">{stats.semana.ventas} esta semana</p>
          </div>
          <div className="bg-graphite rounded-md p-4 border-l-2 border-deep-violet">
            <p className="text-[10px] text-fog-grey uppercase tracking-wider">Monto Hoy</p>
            <p className="text-2xl font-[590] text-porcelain mt-1">{fmtMonto(stats.hoy.monto)}</p>
            <p className="text-[11px] text-storm-cloud mt-0.5">ventas del dia</p>
          </div>
        </div>
      )}

      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex gap-1.5">
          {["", "lead_nuevo", "gestion", "venta"].map((t) => (
            <button
              key={t}
              onClick={() => setTipo(t)}
              className={"text-xs px-3 py-1.5 rounded-full font-[510] transition-colors " + (
                tipo === t
                  ? "bg-neon-lime text-pitch-black"
                  : "bg-charcoal-grey text-storm-cloud hover:text-porcelain"
              )}
            >
              {t === "" ? "Todos" : TIPO_LABEL[t]}
            </button>
          ))}
        </div>

        <select
          value={enterpriseId}
          onChange={(e) => setEnterpriseId(e.target.value)}
          className="bg-pitch-black border border-charcoal-grey rounded-md px-3 py-2 text-porcelain text-sm focus:border-neon-lime focus:outline-none"
        >
          <option value="">Todas UN</option>
          {Object.entries(UN_MAP).map(([id, name]) => (
            <option key={id} value={id}>{name}</option>
          ))}
        </select>

        <select
          value={fuente}
          onChange={(e) => setFuente(e.target.value)}
          className="bg-pitch-black border border-charcoal-grey rounded-md px-3 py-2 text-porcelain text-sm focus:border-neon-lime focus:outline-none"
        >
          <option value="">Todas fuentes</option>
          <option value="Botmaker">Botmaker</option>
          <option value="ThinkChat">ThinkChat</option>
          <option value="Manual">Manual</option>
        </select>

        <span className="text-xs text-fog-grey ml-auto">{total} eventos</span>
      </div>

      {error && <p className="text-warning-red text-sm">{error}</p>}

      {loading && (
        <div className="space-y-3">
          {[1,2,3,4,5].map((i) => (
            <div key={i} className="bg-graphite rounded-md p-5 animate-pulse">
              <div className="h-3 bg-charcoal-grey rounded w-24 mb-2" />
              <div className="h-4 bg-charcoal-grey rounded w-48 mb-1" />
              <div className="h-3 bg-charcoal-grey rounded w-32" />
            </div>
          ))}
        </div>
      )}

      {!loading && eventos.length > 0 && (
        <div className="relative pl-8 max-w-3xl">
          <div className="absolute left-[15px] top-3 bottom-3 w-px bg-charcoal-grey" />
          <div className="space-y-1">
            {eventos.map((evt, i) => (
              <div key={evt.tipo + "-" + evt.lead_id + "-" + i} className="relative pb-4 last:pb-0">
                <div className={"absolute left-[-17px] top-2.5 w-2.5 h-2.5 rounded-full " + (TIPO_DOT[evt.tipo] || "bg-storm-cloud") + " ring-2 ring-pitch-black"} />

                <div
                  className={"bg-graphite rounded-md p-4 border-l-2 " + (TIPO_COLOR[evt.tipo] || "border-storm-cloud") + " cursor-pointer hover:bg-deep-slate/50 transition-colors"}
                  onClick={() => goToLead(evt.lead_id)}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1.5">
                        <span className="text-sm">{TIPO_ICON[evt.tipo]}</span>
                        <span className="text-xs font-[510] text-porcelain">{TIPO_LABEL[evt.tipo]}</span>
                        <span className="text-[11px] text-fog-grey">{evt.relativo}</span>
                        <span className={"text-[10px] px-2 py-0.5 rounded-full font-[510] " + (FUENTE_COLORS[evt.fuente] || FUENTE_COLORS.Manual)}>
                          {evt.fuente}
                        </span>
                        <span className="text-[10px] text-fog-grey">{evt.un_nombre}</span>
                      </div>

                      <p className="text-sm font-[510] text-porcelain truncate">{evt.fullname}</p>
                      <p className="text-[11px] text-fog-grey">{evt.phone}</p>

                      <div className="flex items-center gap-3 mt-2 text-xs flex-wrap">
                        {evt.tipo === "gestion" && evt.from_status_label && (
                          <span className="text-storm-cloud">
                            <span className="text-fog-grey">{evt.from_status_label}</span>
                            {" \u2192 "}
                            <span className="text-porcelain font-[510]">{evt.status_label}</span>
                          </span>
                        )}
                        {evt.tipo === "venta" && (
                          <>
                            {evt.contract_id && (
                              <a href={"https://sistema.grupoepem.com.py/contracts/" + evt.contract_id} target="_blank" rel="noopener noreferrer"
                                 className="text-aether-blue font-[510] hover:text-neon-lime transition-colors"
                                 onClick={(e) => e.stopPropagation()}>
                                Contrato #{evt.contract_id} ↗
                              </a>
                            )}
                            <span className="text-emerald font-[590]">{fmtMonto(evt.monto)}</span>
                          </>
                        )}
                        {evt.vendedor_nombre && evt.vendedor_id && (
                          <span
                            className="text-light-steel cursor-pointer hover:text-neon-lime transition-colors"
                            onClick={(e) => { e.stopPropagation(); goToSeller(evt.vendedor_id!); }}
                          >
                            <span className="text-fog-grey">Vend: </span>{evt.vendedor_nombre}
                          </span>
                        )}
                        {evt.cerrador_nombre && evt.cerrador_id && (
                          <span
                            className="text-deep-violet cursor-pointer hover:text-neon-lime transition-colors"
                            onClick={(e) => { e.stopPropagation(); goToSeller(evt.cerrador_id!); }}
                          >
                            <span className="text-fog-grey">Cerr: </span>{evt.cerrador_nombre}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="text-[10px] text-fog-grey text-right shrink-0 whitespace-nowrap">
                      {fmt(evt.timestamp)}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {!loading && eventos.length === 0 && (
        <div className="bg-graphite rounded-md p-8 text-center max-w-3xl">
          <p className="text-storm-cloud text-sm">Sin actividad reciente con los filtros actuales.</p>
          <p className="text-fog-grey text-xs mt-1">Proba Sync Todo o amplia los filtros.</p>
        </div>
      )}
    </div>
  );
}