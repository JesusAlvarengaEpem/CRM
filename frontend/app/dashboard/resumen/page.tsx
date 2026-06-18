"use client";

import { useState, useEffect, useCallback } from "react";

interface Totales {
  leads: number; ventas: number; conversion: number; monto: number; caliente: number; fria: number;
  ventas_calientes: number; ventas_frias: number;
  ventas_de_leads: number; ventas_externas: number;
}
interface PorUN {
  enterprise_id: number; un_nombre: string; leads: number; ventas: number;
  conversion: number; caliente: number; fria: number; monto: number;
  ventas_calientes: number; ventas_frias: number;
}
interface PorOrigen {
  origen: string; leads: number; ventas: number; conversion: number; caliente: number; fria: number;
}
interface CarteraPorUN { [un: string]: { Caliente: number; Fria: number }; }
interface ResumenResponse {
  rango: { dias: number };
  totales: Totales;
  por_un: PorUN[];
  por_origen: PorOrigen[];
  cartera_por_un: CarteraPorUN;
}

const FUENTE_COLORS: Record<string, string> = {
  ThinkChat: "bg-emerald/20 text-emerald",
  "ThinkChat->Venta": "bg-emerald/20 text-emerald",
  Botmaker: "bg-aether-blue/20 text-aether-blue",
  Externo: "bg-deep-violet/20 text-deep-violet",
  Manual: "bg-fog-grey/20 text-light-steel",
};

function fmtMonto(m: number | null | undefined): string {
  if (m == null || m === 0) return "\u2014";
  if (m >= 1_000_000) return "Gs " + (m / 1_000_000).toFixed(1) + "M";
  return "Gs " + m.toLocaleString("es-PY");
}

export default function ResumenPage() {
  const [data, setData] = useState<ResumenResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [modo, setModo] = useState<string>("7d"); // "hoy" | "7d" | "mes" | "rango"
  const [dias, setDias] = useState(7);
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [mesSelect, setMesSelect] = useState("");

  const fetchResumen = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const token = localStorage.getItem("token");
      const params = new URLSearchParams();
      if (modo === "rango" && desde && hasta) {
        params.set("desde", desde);
        params.set("hasta", hasta);
      } else if (modo === "mes" && mesSelect) {
        const [y, m] = mesSelect.split("-");
        const primerDia = y + "-" + m + "-01";
        const ultimoDia = y + "-" + m + "-" + new Date(parseInt(y), parseInt(m), 0).getDate();
        params.set("desde", primerDia);
        params.set("hasta", ultimoDia);
      } else {
        params.set("dias", String(dias));
      }
      const res = await fetch("http://localhost:8000/api/dashboard/resumen?" + params, {
        headers: { Authorization: "Bearer " + token },
      });
      if (!res.ok) throw new Error("Error al cargar resumen");
      setData(await res.json());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [modo, dias, desde, hasta, mesSelect]);

  useEffect(() => { fetchResumen(); }, [fetchResumen]);

  const meses = (() => {
    const result: {val: string, label: string}[] = [];
    const now = new Date();
    for (let i = 0; i < 12; i++) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      const val = d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0");
      const label = d.toLocaleDateString("es-PY", { month: "long", year: "numeric" });
      result.push({ val, label });
    }
    return result;
  })();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-[590] text-porcelain tracking-[-0.22px]">Resumen Ejecutivo</h1>
          <p className="text-storm-cloud text-sm mt-1">Carteras ingresadas, ventas y mix por unidad de negocio</p>
        </div>
        <div className="flex items-center gap-3">
          {/* Chips de modo */}
          <div className="flex gap-1.5">
            {[
              { id: "hoy", label: "Hoy", dias: 1 },
              { id: "7d", label: "7d", dias: 7 },
              { id: "30d", label: "30d", dias: 30 },
              { id: "mes", label: "Mes", dias: null },
              { id: "rango", label: "Rango", dias: null },
            ].map((m) => (
              <button
                key={m.id}
                onClick={() => {
                  setModo(m.id);
                  if (m.dias) setDias(m.dias);
                }}
                className={"text-xs px-3 py-1.5 rounded-full font-[510] transition-colors " + (
                  modo === m.id ? "bg-neon-lime text-pitch-black" : "bg-charcoal-grey text-storm-cloud hover:text-porcelain"
                )}
              >
                {m.label}
              </button>
            ))}
          </div>

          {/* Selector de mes */}
          {modo === "mes" && (
            <select
              value={mesSelect}
              onChange={(e) => setMesSelect(e.target.value)}
              className="bg-pitch-black border border-charcoal-grey rounded-md px-3 py-2 text-porcelain text-sm focus:border-neon-lime focus:outline-none"
            >
              <option value="">Seleccionar mes</option>
              {meses.map((m) => (
                <option key={m.val} value={m.val}>{m.label}</option>
              ))}
            </select>
          )}

          {/* Date pickers rango */}
          {modo === "rango" && (
            <div className="flex items-center gap-2">
              <input type="date" value={desde} onChange={(e) => setDesde(e.target.value)}
                className="bg-pitch-black border border-charcoal-grey rounded-md px-3 py-2 text-porcelain text-sm focus:border-neon-lime focus:outline-none" />
              <span className="text-fog-grey text-sm">{"\u2192"}</span>
              <input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)}
                className="bg-pitch-black border border-charcoal-grey rounded-md px-3 py-2 text-porcelain text-sm focus:border-neon-lime focus:outline-none" />
            </div>
          )}
        </div>
      </div>

      {error && <p className="text-warning-red text-sm">{error}</p>}

      {/* KPI Cards */}
      {data?.totales && (
        <div className="grid grid-cols-5 gap-4">
          <div className="bg-graphite rounded-md p-4 border-l-2 border-neon-lime">
            <p className="text-[10px] text-fog-grey uppercase tracking-wider">Leads Ingresados</p>
            <p className="text-2xl font-[590] text-porcelain mt-1">{data.totales.leads}</p>
            <p className="text-[11px] text-storm-cloud mt-0.5">{data?.rango?.label || (dias + " dias")}</p>
          </div>
          <div className="bg-graphite rounded-md p-4 border-l-2 border-emerald">
            <p className="text-[10px] text-fog-grey uppercase tracking-wider">Ventas de Leads</p>
            <p className="text-2xl font-[590] text-porcelain mt-1">{data.totales.ventas_de_leads}</p>
            <p className="text-[11px] text-storm-cloud mt-0.5">{data.totales.conversion}% conversion</p>
          </div>
          <div className="bg-graphite rounded-md p-4 border-l-2 border-aether-blue">
            <p className="text-[10px] text-fog-grey uppercase tracking-wider">Ventas Externas</p>
            <p className="text-2xl font-[590] text-porcelain mt-1">{data.totales.ventas_externas}</p>
            <p className="text-[11px] text-storm-cloud mt-0.5">sin lead previo</p>
          </div>
          <div className="bg-graphite rounded-md p-4 border-l-2 border-deep-violet">
            <p className="text-[10px] text-fog-grey uppercase tracking-wider">Ventas Totales</p>
            <p className="text-2xl font-[590] text-porcelain mt-1">{data.totales.ventas}</p>
            <p className="text-[11px] text-storm-cloud mt-0.5">{fmtMonto(data.totales.monto)}</p>
          </div>
          <div className="bg-graphite rounded-md p-4 border-l-2 border-cyan-spark">
            <p className="text-[10px] text-fog-grey uppercase tracking-wider">Ventas</p>
            <p className="text-2xl font-[590] text-porcelain mt-1">
              <span className="text-emerald">{data.totales.ventas_calientes}</span>
              <span className="text-fog-grey mx-1">/</span>
              <span className="text-aether-blue">{data.totales.ventas_frias}</span>
            </p>
            <p className="text-[11px] text-storm-cloud mt-0.5">caliente / fria</p>
          </div>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="space-y-3">
          {[1,2,3].map((i) => (
            <div key={i} className="bg-graphite rounded-md p-5 animate-pulse">
              <div className="h-4 bg-charcoal-grey rounded w-48 mb-3" />
              <div className="h-3 bg-charcoal-grey rounded w-full mb-2" />
              <div className="h-3 bg-charcoal-grey rounded w-3/4" />
            </div>
          ))}
        </div>
      )}

      {/* Por Unidad de Negocio */}
      {!loading && data?.por_un && (
        <div>
          <h2 className="text-sm font-[510] text-storm-cloud uppercase tracking-wider mb-3">Por Unidad de Negocio</h2>
          <div className="bg-graphite rounded-md overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-charcoal-grey text-fog-grey text-[10px] uppercase tracking-wider">
                  <th className="text-left px-4 py-2">UN</th>
                  <th className="text-right px-4 py-2">Leads</th>
                  <th className="text-right px-4 py-2">Ventas</th>
                  <th className="text-right px-4 py-2">Conv %</th>
                  <th className="text-right px-4 py-2 text-emerald">V.Caliente</th>
                  <th className="text-right px-4 py-2 text-aether-blue">V.Fria</th>
                  <th className="text-right px-4 py-2 text-emerald">Monto</th>
                </tr>
              </thead>
              <tbody>
                {data.por_un.map((u) => (
                  <tr key={u.enterprise_id} className="border-b border-charcoal-grey/50 hover:bg-deep-slate/30">
                    <td className="px-4 py-2.5 text-porcelain font-[510]">{u.un_nombre}</td>
                    <td className="px-4 py-2.5 text-right text-porcelain">{u.leads}</td>
                    <td className="px-4 py-2.5 text-right text-emerald font-[510]">{u.ventas}</td>
                    <td className="px-4 py-2.5 text-right text-light-steel">{u.conversion}%</td>
                    <td className="px-4 py-2.5 text-right text-emerald">{u.ventas_calientes}</td>
                    <td className="px-4 py-2.5 text-right text-aether-blue">{u.ventas_frias}</td>
                    <td className="px-4 py-2.5 text-right text-emerald font-[510]">{fmtMonto(u.monto)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Por Origen */}
      {!loading && data?.por_origen && (
        <div>
          <h2 className="text-sm font-[510] text-storm-cloud uppercase tracking-wider mb-3">Por Origen</h2>
          <div className="bg-graphite rounded-md overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-charcoal-grey text-fog-grey text-[10px] uppercase tracking-wider">
                  <th className="text-left px-4 py-2">Fuente</th>
                  <th className="text-right px-4 py-2">Leads</th>
                  <th className="text-right px-4 py-2">Ventas</th>
                  <th className="text-right px-4 py-2">Conv %</th>
                  <th className="text-right px-4 py-2 text-emerald">Caliente</th>
                  <th className="text-right px-4 py-2 text-aether-blue">Fria</th>
                </tr>
              </thead>
              <tbody>
                {data.por_origen.map((o) => (
                  <tr key={o.origen} className="border-b border-charcoal-grey/50 hover:bg-deep-slate/30">
                    <td className="px-4 py-2.5">
                      <span className={"text-[10px] px-2 py-0.5 rounded-full font-[510] " + (FUENTE_COLORS[o.origen] || FUENTE_COLORS.Manual)}>{o.origen}</span>
                    </td>
                    <td className="px-4 py-2.5 text-right text-porcelain">{o.leads}</td>
                    <td className="px-4 py-2.5 text-right text-emerald font-[510]">{o.ventas}</td>
                    <td className="px-4 py-2.5 text-right text-light-steel">{o.conversion}%</td>
                    <td className="px-4 py-2.5 text-right text-emerald">{o.caliente}</td>
                    <td className="px-4 py-2.5 text-right text-aether-blue">{o.fria}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Cartera cruzada por UN */}
      {!loading && data?.cartera_por_un && Object.keys(data.cartera_por_un).length > 0 && (
        <div>
          <h2 className="text-sm font-[510] text-storm-cloud uppercase tracking-wider mb-3">Cartera por UN</h2>
          <div className="bg-graphite rounded-md overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-charcoal-grey text-fog-grey text-[10px] uppercase tracking-wider">
                  <th className="text-left px-4 py-2">UN</th>
                  <th className="text-right px-4 py-2 text-emerald">Caliente</th>
                  <th className="text-right px-4 py-2 text-aether-blue">Fria</th>
                  <th className="text-right px-4 py-2">Total</th>
                  <th className="text-right px-4 py-2">% Caliente</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(data.cartera_por_un).map(([un, c]) => {
                  const total = (c.Caliente || 0) + (c.Fria || 0);
                  const pct = total > 0 ? Math.round((c.Caliente || 0) / total * 100) : 0;
                  return (
                    <tr key={un} className="border-b border-charcoal-grey/50 hover:bg-deep-slate/30">
                      <td className="px-4 py-2.5 text-porcelain font-[510]">{un}</td>
                      <td className="px-4 py-2.5 text-right text-emerald">{c.Caliente || 0}</td>
                      <td className="px-4 py-2.5 text-right text-aether-blue">{c.Fria || 0}</td>
                      <td className="px-4 py-2.5 text-right text-porcelain font-[510]">{total}</td>
                      <td className="px-4 py-2.5 text-right text-light-steel">{pct}%</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}