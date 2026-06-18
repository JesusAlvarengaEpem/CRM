"use client";
import { useState, useEffect } from "react";

interface FunnelData { status_1_nuevo: number; status_5_seguimiento: number; status_10_cotizado: number; status_15_venta: number; activacion_pct: number; cierre_desde_5_pct: number; pasan_por_10_pct: number; cierran_sin_cotizar: number; conversion_total_pct: number; }
interface AgingData { "30+": number; "15-30": number; "7-15": number; "<7": number; }
interface ResponseData { avg_horas: number; median_horas: number; total_gestionados: number; }
interface PipelineUN { enterprise_id: number; un_nombre: string; statuses: Record<number, { leads: number; pct: number }>; }
interface FuenteRow { fuente: string; leads: number; ventas: number; tasa_conversion: number; }
interface RevenueRow { enterprise_id: number; enterprise_name: string; vouchers: number; monto_total: number; monto_millones: number; }
interface Performer { seller_id: number; fullname: string; leads: number; gestionados: number; ventas: number; conversion: number; }
interface PerformerGroup { dias: number; top5: Performer[]; bottom5: Performer[]; total_vendedores: number; }
interface TrendRow { mes_str: string; leads: number; ventas: number; tasa_conversion: number; delta_leads_pct: number | null; delta_ventas_pct: number | null; }
interface UNRow { enterprise_id: number; un_nombre: string; leads: number; ventas: number; tasa_conversion: number; vendedores_activos: number; }
interface TimeClose { avg_dias: number; total_ventas: number; median_dias: number; }

interface MetricasData {
  funnel: FunnelData;
  aging: AgingData;
  response_time: ResponseData;
  pipeline_health: PipelineUN[];
  por_fuente: FuenteRow[];
  revenue_epem: RevenueRow[];
  performers: { ultimos_30_dias: PerformerGroup; ultimos_60_dias: PerformerGroup; ultimos_90_dias: PerformerGroup };
  trends_mensuales: TrendRow[];
  por_un: UNRow[];
  time_to_close: TimeClose;
}

const STATUS_LABELS: Record<number, string> = { 1: "Nuevo", 5: "Seguimiento", 10: "Cotizado", 15: "Venta" };
const STATUS_COLORS: Record<number, string> = { 1: "bg-storm-cloud", 5: "bg-aether-blue", 10: "bg-amber-300", 15: "bg-emerald" };

export default function MetricasPage() {
  const [data, setData] = useState<MetricasData | null>(null);
  const [loading, setLoading] = useState(true);
  const [perfTab, setPerfTab] = useState<"ultimos_30_dias" | "ultimos_60_dias" | "ultimos_90_dias">("ultimos_30_dias");

  useEffect(() => {
    const t = localStorage.getItem("token"); if (!t) return;
    fetch("/api/dashboard/metricas", { headers: { Authorization: `Bearer ${t}` } })
      .then(r => r.json()).then(d => { setData(d); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  if (loading || !data) return <div className="space-y-4">{[...Array(8)].map((_, i) => <div key={i} className="h-20 bg-graphite rounded animate-pulse" />)}</div>;

  const f = data.funnel;
  const maxFunnel = Math.max(f.status_1_nuevo, f.status_5_seguimiento, f.status_10_cotizado, f.status_15_venta);
  const totalMonto = data.revenue_epem.reduce((s, e) => s + (e.monto_total || 0), 0);
  const maxTrend = Math.max(...data.trends_mensuales.map(t => t.leads), 1);
  const perf = data.performers[perfTab];

  return <div className="space-y-6">
    <h1 className="text-2xl font-[590] text-porcelain tracking-[-0.22px]">Métricas</h1>
    <p className="text-storm-cloud text-sm -mt-4">Funnel · Aging · Pipeline Health · Performers · Revenue · Trends</p>

    {/* ── TOP CARDS ── */}
    <div className="grid grid-cols-5 gap-3">
      <div className="bg-graphite rounded-md p-4 border-l-2 border-emerald">
        <p className="text-storm-cloud text-[10px] uppercase">Conv. Total</p>
        <p className="text-3xl font-[590] text-emerald mt-1">{f.conversion_total_pct}%</p>
        <p className="text-fog-grey text-[10px] mt-1">{f.status_15_venta.toLocaleString()} ventas</p>
      </div>
      <div className="bg-graphite rounded-md p-4 border-l-2 border-aether-blue">
        <p className="text-storm-cloud text-[10px] uppercase">Activación</p>
        <p className="text-3xl font-[590] text-aether-blue mt-1">{f.activacion_pct}%</p>
        <p className="text-fog-grey text-[10px] mt-1">1 → 5</p>
      </div>
      <div className="bg-graphite rounded-md p-4 border-l-2 border-warning-red">
        <p className="text-storm-cloud text-[10px] uppercase">Abandono +30d</p>
        <p className="text-3xl font-[590] text-warning-red mt-1">{data.aging["30+"].toLocaleString()}</p>
        <p className="text-fog-grey text-[10px] mt-1">leads stuck en status 1</p>
      </div>
      <div className="bg-graphite rounded-md p-4 border-l-2 border-deep-violet">
        <p className="text-storm-cloud text-[10px] uppercase">T. Respuesta</p>
        <p className="text-3xl font-[590] text-deep-violet mt-1">{Math.round(data.response_time.median_horas)}h</p>
        <p className="text-fog-grey text-[10px] mt-1">mediana</p>
      </div>
      <div className="bg-graphite rounded-md p-4 border-l-2 border-neon-lime">
        <p className="text-storm-cloud text-[10px] uppercase">Revenue EPEM</p>
        <p className="text-3xl font-[590] text-neon-lime mt-1">{Math.round(totalMonto / 1_000_000_000)}B</p>
        <p className="text-fog-grey text-[10px] mt-1">{totalMonto.toLocaleString()} Gs</p>
      </div>
    </div>

    {/* ── FUNNEL ── */}
    <div className="bg-graphite rounded-md p-5">
      <h2 className="text-sm font-[590] text-porcelain mb-4">Funnel de Conversión</h2>
      <div className="flex items-end gap-2 h-32 mb-3">
        {[
          { label: "Nuevo", value: f.status_1_nuevo, status: 1 },
          { label: "Seguimiento", value: f.status_5_seguimiento, status: 5 },
          { label: "Cotizado", value: f.status_10_cotizado, status: 10 },
          { label: "Venta", value: f.status_15_venta, status: 15 },
        ].map((stage, i) => (
          <div key={i} className="flex-1 flex flex-col items-center gap-1">
            <span className="text-[10px] text-porcelain font-[590]">{stage.value >= 1000 ? `${(stage.value / 1000).toFixed(0)}k` : stage.value}</span>
            <div className={`w-full rounded-t ${STATUS_COLORS[stage.status]}`} style={{ height: `${(stage.value / maxFunnel) * 100}%`, minHeight: 4 }} />
            <span className="text-[10px] text-storm-cloud">{stage.label}</span>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-4 gap-2 text-[10px]">
        <div className="text-center"><span className="text-storm-cloud">Activación: </span><span className="text-aether-blue font-[590]">{f.activacion_pct}%</span></div>
        <div className="text-center"><span className="text-storm-cloud">Cierre desde 5: </span><span className="text-emerald font-[590]">{f.cierre_desde_5_pct}%</span></div>
        <div className="text-center"><span className="text-storm-cloud">Pasan por cotización: </span><span className="text-amber-300 font-[590]">{f.pasan_por_10_pct}%</span></div>
        <div className="text-center"><span className="text-storm-cloud">Cierran sin cotizar: </span><span className="text-warning-red font-[590]">{f.cierran_sin_cotizar.toLocaleString()}</span></div>
      </div>
    </div>

    {/* ── AGING + RESPONSE TIME ── */}
    <div className="grid grid-cols-2 gap-4">
      <div className="bg-graphite rounded-md p-5">
        <h2 className="text-sm font-[590] text-porcelain mb-3">Aging — Leads en Status 1</h2>
        <div className="grid grid-cols-4 gap-2">
          {[
            { label: "<7 días", key: "<7", color: "text-emerald" },
            { label: "7-15 días", key: "7-15", color: "text-neon-lime" },
            { label: "15-30 días", key: "15-30", color: "text-amber-300" },
            { label: "30+ días", key: "30+", color: "text-warning-red" },
          ].map(b => (
            <div key={b.key} className="bg-pitch-black rounded p-3 text-center">
              <p className={`text-xl font-[590] ${b.color}`}>{(data.aging[b.key as keyof AgingData] || 0).toLocaleString()}</p>
              <p className="text-fog-grey text-[10px] mt-1">{b.label}</p>
            </div>
          ))}
        </div>
      </div>
      <div className="bg-graphite rounded-md p-5">
        <h2 className="text-sm font-[590] text-porcelain mb-3">Tiempo de Respuesta</h2>
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-pitch-black rounded p-4">
            <p className="text-storm-cloud text-[10px] uppercase">Promedio</p>
            <p className="text-2xl font-[590] text-aether-blue mt-1">{Math.round(data.response_time.avg_horas)}h</p>
            <p className="text-fog-grey text-[10px] mt-1">desde first_seen</p>
          </div>
          <div className="bg-pitch-black rounded p-4">
            <p className="text-storm-cloud text-[10px] uppercase">Mediana</p>
            <p className="text-2xl font-[590] text-deep-violet mt-1">{Math.round(data.response_time.median_horas)}h</p>
            <p className="text-fog-grey text-[10px] mt-1">50th percentile</p>
          </div>
        </div>
        <p className="text-fog-grey text-[10px] mt-3">{data.response_time.total_gestionados.toLocaleString()} leads gestionados</p>
      </div>
    </div>

    {/* ── PIPELINE HEALTH ── */}
    <div className="bg-graphite rounded-md p-5">
      <h2 className="text-sm font-[590] text-porcelain mb-4">Pipeline Health — % Cartera por Status</h2>
      <div className="grid grid-cols-4 gap-3">
        {data.pipeline_health.filter(un => un.un_nombre.includes("Odontologia") || un.un_nombre.includes("Estetica") || un.un_nombre.includes("Prepaga") || un.un_nombre.includes("Emergencias")).map(un => (
          <div key={un.enterprise_id} className="bg-pitch-black rounded p-3">
            <p className="text-light-steel text-xs font-[510] mb-2">{un.un_nombre}</p>
            <div className="flex h-3 rounded-full overflow-hidden">
              {[1, 5, 10, 15].map(s => {
                const pct = un.statuses[s]?.pct || 0;
                return pct > 0 ? <div key={s} className={`${STATUS_COLORS[s]} h-full`} style={{ width: `${pct}%` }} title={`${STATUS_LABELS[s]}: ${pct}%`} /> : null;
              })}
            </div>
            <div className="flex justify-between text-[9px] mt-1.5 text-fog-grey">
              {[1, 5, 10, 15].map(s => <span key={s}>{STATUS_LABELS[s].slice(0, 3)} {un.statuses[s]?.pct || 0}%</span>)}
            </div>
          </div>
        ))}
      </div>
    </div>

    {/* ── PERFORMERS ── */}
    <div className="bg-graphite rounded-md p-5">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-sm font-[590] text-porcelain">Top & Bottom Performers</h2>
        <div className="flex gap-1">
          {(["ultimos_30_dias", "ultimos_60_dias", "ultimos_90_dias"] as const).map(tab => (
            <button key={tab} onClick={() => setPerfTab(tab)}
              className={`px-3 py-1 text-xs rounded ${perfTab === tab ? "bg-neon-lime text-pitch-black font-[590]" : "bg-pitch-black text-storm-cloud hover:text-porcelain"}`}>
              {tab === "ultimos_30_dias" ? "30d" : tab === "ultimos_60_dias" ? "60d" : "90d"}
            </button>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-emerald text-xs font-[510] mb-2">▲ Top 5 ({perf.total_vendedores} vendedores)</p>
          <table className="w-full text-xs">
            <thead><tr className="text-storm-cloud"><th className="text-left py-1">#</th><th className="text-left py-1">Vendedor</th><th className="text-right py-1">Leads</th><th className="text-right py-1">Ventas</th><th className="text-right py-1">Conv.</th></tr></thead>
            <tbody>
              {perf.top5.map((p, i) => (
                <tr key={p.seller_id} className="border-b border-charcoal-grey/30">
                  <td className="py-1 text-fog-grey">{i + 1}</td>
                  <td className="py-1 text-porcelain">{p.fullname}</td>
                  <td className="py-1 text-right text-light-steel">{p.leads}</td>
                  <td className="py-1 text-right text-porcelain font-[590]">{p.ventas}</td>
                  <td className="py-1 text-right text-emerald font-[590]">{p.conversion}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div>
          <p className="text-warning-red text-xs font-[510] mb-2">▼ Bottom 5</p>
          <table className="w-full text-xs">
            <thead><tr className="text-storm-cloud"><th className="text-left py-1">#</th><th className="text-left py-1">Vendedor</th><th className="text-right py-1">Leads</th><th className="text-right py-1">Ventas</th><th className="text-right py-1">Conv.</th></tr></thead>
            <tbody>
              {perf.bottom5.map((p, i) => (
                <tr key={p.seller_id} className="border-b border-charcoal-grey/30">
                  <td className="py-1 text-fog-grey">{perf.total_vendedores - perf.bottom5.length + i + 1}</td>
                  <td className="py-1 text-porcelain">{p.fullname}</td>
                  <td className="py-1 text-right text-light-steel">{p.leads}</td>
                  <td className="py-1 text-right text-porcelain font-[590]">{p.ventas}</td>
                  <td className="py-1 text-right text-warning-red font-[590]">{p.conversion}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>

    {/* ── REVENUE x FUENTE + CONVERSIÓN x UN ── */}
    <div className="grid grid-cols-2 gap-4">
      <div className="bg-graphite rounded-md p-5">
        <h2 className="text-sm font-[590] text-porcelain mb-4">Revenue x Fuente</h2>
        <div className="space-y-3">
          {data.por_fuente.map(f => (
            <div key={f.fuente}>
              <div className="flex justify-between text-xs mb-1"><span className="text-light-steel">{f.fuente}</span><span className="text-porcelain font-[590]">{f.leads.toLocaleString()} leads · {f.ventas} ventas · {f.tasa_conversion}% conv</span></div>
              <div className="h-2 bg-pitch-black rounded-full overflow-hidden"><div className="h-full rounded-full bg-aether-blue/70" style={{ width: `${(f.leads / Math.max(...data.por_fuente.map(x => x.leads), 1)) * 100}%` }} /></div>
            </div>
          ))}
        </div>
      </div>
      <div className="bg-graphite rounded-md p-5">
        <h2 className="text-sm font-[590] text-porcelain mb-4">Conversión x UN</h2>
        <div className="space-y-3">
          {data.por_un.map(u => (
            <div key={u.enterprise_id}>
              <div className="flex justify-between text-xs mb-1"><span className="text-light-steel">{u.un_nombre}</span><span className="text-porcelain font-[590]">{u.leads.toLocaleString()} leads · {u.tasa_conversion}% conv</span></div>
              <div className="h-2 bg-pitch-black rounded-full overflow-hidden"><div className="h-full rounded-full bg-emerald/70" style={{ width: `${Math.min(100, u.tasa_conversion * 5)}%` }} /></div>
            </div>
          ))}
        </div>
      </div>
    </div>

    {/* ── REVENUE EPEM ── */}
    {data.revenue_epem.length > 0 && !data.revenue_epem[0].error && (
      <div className="bg-graphite rounded-md p-5">
        <h2 className="text-sm font-[590] text-porcelain mb-4">Revenue x UN (EPEM Vouchers)</h2>
        <div className="grid grid-cols-4 gap-3">
          {data.revenue_epem.slice(0, 8).map(e => (
            <div key={e.enterprise_id} className="bg-pitch-black rounded p-3"><p className="text-light-steel text-xs">{e.enterprise_name}</p><p className="text-porcelain font-[590] text-lg mt-1">{e.monto_millones.toLocaleString()}M Gs</p><p className="text-fog-grey text-[10px]">{e.vouchers.toLocaleString()} vouchers</p></div>
          ))}
        </div>
      </div>
    )}

    {/* ── TRENDS MENSUALES ── */}
    <div className="bg-graphite rounded-md p-5">
      <h2 className="text-sm font-[590] text-porcelain mb-4">Trends Mensuales (12 meses)</h2>
      <div className="flex items-end gap-1 h-40">
        {data.trends_mensuales.map((t, i) => (
          <div key={i} className="flex-1 flex flex-col items-center gap-1" title={`${t.mes_str}: ${t.leads} leads${t.delta_leads_pct !== null ? ` (${t.delta_leads_pct >= 0 ? "+" : ""}${t.delta_leads_pct}%)` : ""}`}>
            <span className={`text-[9px] ${t.delta_leads_pct !== null ? (t.delta_leads_pct >= 0 ? "text-emerald" : "text-warning-red") : "text-storm-cloud"}`}>
              {t.leads >= 1000 ? `${(t.leads / 1000).toFixed(0)}k` : t.leads}
              {t.delta_leads_pct !== null && <span className="ml-0.5">{t.delta_leads_pct >= 0 ? "↑" : "↓"}{Math.abs(t.delta_leads_pct)}%</span>}
            </span>
            <div className="w-full bg-aether-blue rounded-t" style={{ height: `${(t.leads / maxTrend) * 100}%`, minHeight: 2 }} />
            <span className="text-[9px] text-fog-grey">{t.mes_str.slice(5)}</span>
          </div>
        ))}
      </div>
    </div>

    {/* ── TIME TO CLOSE ── */}
    <div className="grid grid-cols-3 gap-3">
      <div className="bg-graphite rounded-md p-4 border-l-2 border-emerald"><p className="text-storm-cloud text-[10px] uppercase">Avg Time to Close</p><p className="text-2xl font-[590] text-emerald mt-2">{data.time_to_close.avg_dias}d</p><p className="text-fog-grey text-[10px] mt-1">{data.time_to_close.total_ventas.toLocaleString()} ventas</p></div>
      <div className="bg-graphite rounded-md p-4 border-l-2 border-aether-blue"><p className="text-storm-cloud text-[10px] uppercase">Median Time</p><p className="text-2xl font-[590] text-aether-blue mt-2">{Math.round(data.time_to_close.median_dias)}d</p><p className="text-fog-grey text-[10px] mt-1">50th percentile</p></div>
      <div className="bg-graphite rounded-md p-4 border-l-2 border-deep-violet"><p className="text-storm-cloud text-[10px] uppercase">Cierran sin cotizar</p><p className="text-2xl font-[590] text-deep-violet mt-2">{f.cierran_sin_cotizar.toLocaleString()}</p><p className="text-fog-grey text-[10px] mt-1">de {f.status_15_venta.toLocaleString()} ventas</p></div>
    </div>
  </div>;
}
