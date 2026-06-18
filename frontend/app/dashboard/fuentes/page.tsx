"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

interface FuenteTotales {
  leads: number;
  ventas: number;
  gestionados: number;
  conversion: number;
  share_pct: number;
}

interface ComparacionBMvsTC {
  botmaker: FuenteTotales;
  thinkchat: FuenteTotales;
  ratio_bm_tc_leads: number | null;
  ratio_bm_tc_ventas: number | null;
}

interface SerieMensual {
  mes: string;
  fuentes: Record<string, FuenteTotales>;
}

interface FuentesData {
  modo: string;
  meses_consultados: number;
  total_general: number;
  fuentes: string[];
  totales_por_fuente: Record<string, FuenteTotales>;
  comparacion_bm_vs_tc: ComparacionBMvsTC;
  serie_mensual: SerieMensual[];
}

interface UnidadTotales {
  leads: number;
  ventas: number;
  gestionados: number;
  conversion: number;
  por_fuente: Record<string, { leads: number; ventas: number }>;
}

interface FuentesPorUnidad {
  modo: string;
  meses_consultados: number;
  unidades_negocio: number[];
  unidades_nombres: Record<number, string>;
  totales_por_unidad: Record<string, UnidadTotales>;
}

const UN_COLORS: Record<string, string> = {
  Botmaker: "bg-aether-blue/20 text-aether-blue border-aether-blue/30",
  ThinkChat: "bg-emerald/20 text-emerald border-emerald/30",
  Manual: "bg-fog-grey/20 text-light-steel border-fog-grey/30",
  Otro: "bg-amber-300/20 text-amber-300 border-amber-300/30",
};

export default function FuentesPage() {
  const router = useRouter();
  const [meses, setMeses] = useState(12);
  const [modo, setModo] = useState<"por_fuente" | "por_unidad">("por_fuente");
  const [data, setData] = useState<FuentesData | FuentesPorUnidad | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Sync ThinkChat
  const [syncStatus, setSyncStatus] = useState("");
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) return;
    setLoading(true);
    setError("");
    const url = `http://localhost:8000/api/dashboard/fuentes-comparacion?meses=${meses}${
      modo === "por_unidad" ? "&por_unidad=true" : ""
    }`;
    const ac = new AbortController();
    const tid = setTimeout(() => ac.abort(), 60000);
    fetch(url, { headers: { Authorization: `Bearer ${token}` }, signal: ac.signal })
      .then((r) => {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then((d) => { setData(d); setLoading(false); })
      .catch((e) => {
        setError(e.name === "AbortError" ? "Timeout: la query tardó más de 60s" : "Error: " + e.message);
        setLoading(false);
      });
    return () => { clearTimeout(tid); ac.abort(); };
  }, [meses, modo]);

  const triggerSync = async () => {
    const token = localStorage.getItem("token");
    if (!token) return;
    setSyncing(true);
    setSyncStatus("Sincronizando con portal ThinkChat... esto puede tardar 1-2 min");
    try {
      const r = await fetch("http://localhost:8000/api/etl/sync/thinkchat", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) throw new Error("HTTP " + r.status);
      const j = await r.json();
      const res = j.result || j;
      if (res.status === "ok") {
        setSyncStatus(
          `OK: ${res.records_upserted} upserted, ${res.duplicates_skipped || 0} duplicados, ` +
          `errores=${res.errors || 0}, duración=${res.duration_sec}s`
        );
        // Refrescar datos
        setMeses((m) => m);
      } else {
        setSyncStatus(`Error: ${res.error || JSON.stringify(res)}`);
      }
    } catch (e: any) {
      setSyncStatus("Error: " + e.message);
    } finally {
      setSyncing(false);
    }
  };

  if (loading && !data) {
    return (
      <div className="space-y-4">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="h-16 bg-graphite rounded animate-pulse" />
        ))}
      </div>
    );
  }
  if (error) {
    return (
      <div className="p-6 bg-graphite rounded border-l-2 border-warning-red">
        <p className="text-warning-red text-sm">{error}</p>
      </div>
    );
  }
  if (!data) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-[590] text-porcelain tracking-[-0.22px]">
            Comparación de Fuentes
          </h1>
          <p className="text-storm-cloud text-sm mt-1">
            Botmaker vs ThinkChat vs Manual â€” volumen, ventas y conversión mes a mes
          </p>
        </div>
        <button
          onClick={triggerSync}
          disabled={syncing}
          className="bg-neon-lime text-pitch-black font-[590] text-sm rounded-md px-4 py-2 hover:opacity-90 transition-opacity disabled:opacity-50"
          title="Auto-descarga Excel del portal ThinkChat y upserts al DW"
        >
          {syncing ? "Sincronizando..." : "Actualizar leads ThinkChat"}
        </button>
      </div>

      {/* Sync status banner */}
      {syncStatus && (
        <div className={`p-3 rounded-md text-sm ${
          syncStatus.startsWith("OK") ? "bg-emerald/10 border border-emerald/30 text-emerald" :
          syncStatus.startsWith("Error") ? "bg-warning-red/10 border border-warning-red/30 text-warning-red" :
          "bg-aether-blue/10 border border-aether-blue/30 text-aether-blue"
        }`}>
          {syncStatus}
        </div>
      )}

      {/* Filtros */}
      <div className="flex gap-2 items-end">
        <div>
          <label className="block text-storm-cloud text-[10px] mb-0.5">Período (meses)</label>
          <select
            value={meses}
            onChange={(e) => setMeses(parseInt(e.target.value))}
            className="bg-pitch-black border border-charcoal-grey rounded px-2 py-1.5 text-porcelain text-xs focus:border-neon-lime focus:outline-none"
          >
            <option value={3}>Últimos 3 meses</option>
            <option value={6}>Últimos 6 meses</option>
            <option value={12}>Últimos 12 meses</option>
            <option value={24}>Últimos 24 meses</option>
          </select>
        </div>
        <div>
          <label className="block text-storm-cloud text-[10px] mb-0.5">Modo</label>
          <select
            value={modo}
            onChange={(e) => setModo(e.target.value as any)}
            className="bg-pitch-black border border-charcoal-grey rounded px-2 py-1.5 text-porcelain text-xs focus:border-neon-lime focus:outline-none"
          >
            <option value="por_fuente">Por Fuente</option>
            <option value="por_unidad">Por Unidad de Negocio</option>
          </select>
        </div>
      </div>

      {modo === "por_fuente" ? (
        <PorFuente data={data as FuentesData} />
      ) : (
        <PorUnidad data={data as FuentesPorUnidad} />
      )}
    </div>
  );
}

function PorFuente({ data }: { data: FuentesData }) {
  const { totales_por_fuente, comparacion_bm_vs_tc, serie_mensual, fuentes, meses_consultados } = data;
  const bm = comparacion_bm_vs_tc.botmaker;
  const tc = comparacion_bm_vs_tc.thinkchat;

  return (
    <>
      {/* KPIs principales: BM vs TC */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-graphite rounded-md p-4 border-l-2 border-aether-blue">
          <p className="text-storm-cloud text-[10px] uppercase tracking-wider">Botmaker</p>
          <p className="text-2xl font-[590] text-aether-blue mt-1">{bm.leads.toLocaleString()}</p>
          <p className="text-fog-grey text-[10px] mt-1">leads · {bm.share_pct}% share</p>
        </div>
        <div className="bg-graphite rounded-md p-4 border-l-2 border-emerald">
          <p className="text-storm-cloud text-[10px] uppercase tracking-wider">ThinkChat</p>
          <p className="text-2xl font-[590] text-emerald mt-1">{tc.leads.toLocaleString()}</p>
          <p className="text-fog-grey text-[10px] mt-1">leads · {tc.share_pct}% share</p>
        </div>
        <div className="bg-graphite rounded-md p-4 border-l-2 border-neon-lime">
          <p className="text-storm-cloud text-[10px] uppercase tracking-wider">Ratio BM/TC</p>
          <p className="text-2xl font-[590] text-neon-lime mt-1">
            {comparacion_bm_vs_tc.ratio_bm_tc_leads ?? "â€”"}
          </p>
          <p className="text-fog-grey text-[10px] mt-1">en leads totales</p>
        </div>
      </div>

      {/* Tabla totales por fuente */}
      <div className="bg-graphite rounded-md overflow-hidden">
        <h2 className="text-sm font-[590] text-porcelain p-4 border-b border-charcoal-grey">
          Totales por fuente · últimos {meses_consultados} meses
        </h2>
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-charcoal-grey text-storm-cloud font-[510]">
              <th className="px-3 py-2 text-left">Fuente</th>
              <th className="px-3 py-2 text-right">Leads</th>
              <th className="px-3 py-2 text-right">Gestionados</th>
              <th className="px-3 py-2 text-right">Ventas</th>
              <th className="px-3 py-2 text-right">Conversión</th>
              <th className="px-3 py-2 text-right">Share</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(totales_por_fuente)
              .sort((a, b) => b[1].leads - a[1].leads)
              .map(([f, v]) => (
                <tr key={f} className="border-b border-charcoal-grey/50 hover:bg-deep-slate/50">
                  <td className="px-3 py-2">
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-[510] ${UN_COLORS[f] || UN_COLORS.Otro}`}>
                      {f}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right text-porcelain font-[510]">{v.leads.toLocaleString()}</td>
                  <td className="px-3 py-2 text-right text-light-steel">{v.gestionados.toLocaleString()}</td>
                  <td className="px-3 py-2 text-right text-porcelain">{v.ventas.toLocaleString()}</td>
                  <td className="px-3 py-2 text-right text-light-steel">{v.conversion}%</td>
                  <td className="px-3 py-2 text-right text-fog-grey">{v.share_pct}%</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      {/* Serie mensual: bar chart-like table */}
      <div className="bg-graphite rounded-md overflow-hidden">
        <h2 className="text-sm font-[590] text-porcelain p-4 border-b border-charcoal-grey">
          Volumen mensual por fuente
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-charcoal-grey text-storm-cloud font-[510]">
                <th className="px-3 py-2 text-left sticky left-0 bg-graphite">Mes</th>
                {fuentes.map((f) => (
                  <th key={f} className="px-3 py-2 text-right">
                    <span className={`text-[10px] px-2 py-0.5 rounded-full ${UN_COLORS[f] || UN_COLORS.Otro}`}>
                      {f}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {serie_mensual.map((m) => (
                <tr key={m.mes} className="border-b border-charcoal-grey/50">
                  <td className="px-3 py-2 text-porcelain font-[510] sticky left-0 bg-graphite">{m.mes}</td>
                  {fuentes.map((f) => {
                    const v = m.fuentes[f];
                    return (
                      <td key={f} className="px-3 py-2 text-right">
                        {v ? (
                          <div>
                            <div className="text-light-steel font-[510]">{v.leads.toLocaleString()}</div>
                            <div className="text-[9px] text-fog-grey">
                              {v.ventas}v · {v.conversion}%
                            </div>
                          </div>
                        ) : (
                          <span className="text-fog-grey/40">â€”</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

function PorUnidad({ data }: { data: FuentesPorUnidad }) {
  const { totales_por_unidad } = data;

  return (
    <>
      {/* Tabla por unidad */}
      <div className="space-y-3">
        {Object.entries(totales_por_unidad)
          .sort((a, b) => b[1].leads - a[1].leads)
          .map(([nombre, v]) => (
            <div key={nombre} className="bg-graphite rounded-md p-4">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="text-sm font-[590] text-porcelain">{nombre}</h3>
                  <p className="text-fog-grey text-[10px] mt-0.5">
                    {v.leads.toLocaleString()} leads · {v.ventas} ventas · {v.conversion}% conv
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-[590] text-neon-lime">{v.conversion}%</p>
                  <p className="text-fog-grey text-[10px]">conversión</p>
                </div>
              </div>
              {/* Mini-barras por fuente dentro de la UN */}
              <div className="space-y-1.5">
                {Object.entries(v.por_fuente)
                  .sort((a, b) => b[1].leads - a[1].leads)
                  .map(([f, fd]) => {
                    const max = Math.max(...Object.values(v.por_fuente).map(x => x.leads), 1);
                    const pct = (fd.leads / max) * 100;
                    return (
                      <div key={f} className="flex items-center gap-2 text-xs">
                        <span className={`w-20 text-[10px] px-2 py-0.5 rounded-full font-[510] ${UN_COLORS[f] || UN_COLORS.Otro}`}>
                          {f}
                        </span>
                        <div className="flex-1 h-4 bg-pitch-black rounded-full overflow-hidden">
                          <div
                            className="h-full bg-aether-blue/70 flex items-center justify-end pr-2"
                            style={{ width: `${pct}%`, minWidth: 2 }}
                          >
                            <span className="text-[9px] text-porcelain font-[510]">
                              {fd.leads.toLocaleString()}
                            </span>
                          </div>
                        </div>
                        <span className="text-fog-grey text-[10px] w-12 text-right">
                          {fd.ventas}v
                        </span>
                      </div>
                    );
                  })}
              </div>
            </div>
          ))}
      </div>
    </>
  );
}

