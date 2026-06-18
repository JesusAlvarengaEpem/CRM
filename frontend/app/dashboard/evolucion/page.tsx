"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

// â”€â”€ Types â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
interface FuenteEvol {
  leads: number;
  ventas: number;
  conversion: number;
  share_pct: number;
}

interface MesEvol {
  mes: string;
  leads: number;
  ventas: number;
  conversion: number;
  delta_leads_pct: number;
  delta_ventas_pct: number;
  fuentes: Record<string, FuenteEvol>;
}

interface TotalesPorFuente {
  leads: number;
  ventas: number;
  conversion: number;
  share_pct: number;
}

interface EvolucionData {
  rango: { desde: string; hasta: string };
  meses_count: number;
  fuentes: string[];
  totales: { leads: number; ventas: number; conversion: number };
  totales_por_fuente: Record<string, TotalesPorFuente>;
  serie_mensual: MesEvol[];
}

// â”€â”€ Color palette â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const FONT_COLORS: Record<string, string> = {
  Botmaker: "#22d3ee",   // cyan
  ThinkChat: "#a3e635",  // lime
  Manual: "#fbbf24",     // amber
  Otro: "#a78bfa",       // violet
};
const DEFAULT_COLOR = "#94a3b8";

// â”€â”€ SVG Line Chart Component â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function LineChart({
  data,
  sources,
  hiddenSources = new Set<string>(),
  width = 900,
  height = 320,
}: {
  data: MesEvol[];
  sources: string[];
  hiddenSources?: Set<string>;
  width?: number;
  height?: number;
}) {
  if (!data.length) return <div className="text-fog-grey text-sm">Sin datos</div>;

  const padding = { top: 20, right: 100, bottom: 40, left: 60 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;

  // Si alguna fuente está oculta, recalcular maxLeads para escalar mejor
  const visibleSources = sources.filter((s) => !hiddenSources.has(s));
  const maxLeads = Math.max(
    ...data.map((d) =>
      visibleSources.length > 0
        ? Math.max(...visibleSources.map((s) => d.fuentes[s]?.leads || 0))
        : d.leads
    )
  ) * 1.1 || 1;
  const maxVentas = Math.max(...data.map((d) => d.ventas)) * 1.1 || 1;

  const xStep = data.length > 1 ? chartW / (data.length - 1) : chartW;
  const x = (i: number) => padding.left + i * xStep;
  const yLeads = (v: number) => padding.top + chartH - (v / maxLeads) * chartH;
  const yVentas = (v: number) => padding.top + chartH - (v / maxVentas) * chartH;

  // 5 grid lines
  const yTicks = 5;
  const yGrid = Array.from({ length: yTicks + 1 }, (_, i) => {
    const ratio = i / yTicks;
    return {
      leads: Math.round(maxLeads * ratio),
      ventas: Math.round(maxVentas * ratio),
      y: padding.top + chartH - chartH * ratio,
    };
  });

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full" style={{ maxWidth: "100%" }}>
      {/* Grid lines + Y axis labels (leads, left) */}
      {yGrid.map((g, i) => (
        <g key={`grid-${i}`}>
          <line
            x1={padding.left} y1={g.y} x2={width - padding.right} y2={g.y}
            stroke="#334155" strokeWidth={0.5} strokeDasharray="2,3"
          />
          <text x={padding.left - 8} y={g.y + 3} fill="#94a3b8" fontSize={10} textAnchor="end">
            {g.leads.toLocaleString("es-PY")}
          </text>
        </g>
      ))}
      {/* Y axis labels (ventas, right) */}
      {yGrid.map((g, i) => (
        <text key={`vgrid-${i}`} x={width - padding.right + 8} y={g.y + 3} fill="#a3e635" fontSize={10} textAnchor="start">
          {g.ventas.toLocaleString("es-PY")}
        </text>
      ))}

      {/* X axis labels (meses) */}
      {data.map((d, i) => (
        <text
          key={`x-${i}`}
          x={x(i)} y={height - padding.bottom + 18}
          fill="#94a3b8" fontSize={10} textAnchor="middle"
        >
          {d.mes}
        </text>
      ))}

      {/* Lines per source: leads (left axis) â€” only visible sources */}
      {visibleSources.map((src) => {
        const color = FONT_COLORS[src] || DEFAULT_COLOR;
        const points = data.map((d, i) => `${x(i)},${yLeads(d.fuentes[src]?.leads || 0)}`).join(" ");
        return (
          <g key={`l-${src}`}>
            <polyline
              points={points}
              fill="none" stroke={color} strokeWidth={1.5} strokeOpacity={0.5}
            />
            {data.map((d, i) => (
              <circle
                key={`c-${src}-${i}`}
                cx={x(i)} cy={yLeads(d.fuentes[src]?.leads || 0)}
                r={3} fill={color}
              />
            ))}
          </g>
        );
      })}

      {/* Sales line: total ventas (right axis), bold lime */}
      <polyline
        points={data.map((d, i) => `${x(i)},${yVentas(d.ventas)}`).join(" ")}
        fill="none" stroke="#a3e635" strokeWidth={2.5}
      />
      {data.map((d, i) => (
        <circle
          key={`v-${i}`}
          cx={x(i)} cy={yVentas(d.ventas)} r={4} fill="#a3e635"
        />
      ))}

      {/* Legend â€” mark hidden sources as faded */}
      {sources.map((src, idx) => {
        const hidden = hiddenSources.has(src);
        const color = FONT_COLORS[src] || DEFAULT_COLOR;
        return (
          <g key={`leg-${src}`} transform={`translate(${width - padding.right + 30}, ${padding.top + idx * 18})`} opacity={hidden ? 0.35 : 1}>
            <circle cx={0} cy={-3} r={4} fill={color} />
            <text x={8} y={0} fill="#cbd5e1" fontSize={11}>{src}</text>
          </g>
        );
      })}
      <g transform={`translate(${width - padding.right + 30}, ${padding.top + sources.length * 18 + 6})`}>
        <circle cx={0} cy={-3} r={4} fill="#a3e635" />
        <text x={8} y={0} fill="#cbd5e1" fontSize={11}>Ventas total</text>
      </g>
    </svg>
  );
}

// â”€â”€ SVG Combo Chart: bars (leads) + line (ventas) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function ComboChart({
  data,
  sources,
  hiddenSources = new Set<string>(),
  width = 900,
  height = 360,
}: {
  data: MesEvol[];
  sources: string[];
  hiddenSources?: Set<string>;
  width?: number;
  height?: number;
}) {
  if (!data.length) return <div className="text-fog-grey text-sm">Sin datos</div>;

  const padding = { top: 20, right: 110, bottom: 40, left: 60 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;

  const visibleSources = sources.filter((s) => !hiddenSources.has(s));

  // Leads por fuente: solo las visibles
  // Ventas: si visibleSources.length === sources.length, usar d.ventas (total).
  //         Si hay fuentes ocultas, sumar solo ventas de las fuentes visibles.
  const dataWithFiltered: { mes: string; leads: number; ventas: number; fuentes: any }[] =
    data.map((d) => {
      const leads = visibleSources.length > 0
        ? visibleSources.reduce((acc, s) => acc + (d.fuentes[s]?.leads || 0), 0)
        : d.leads;
      const ventas = visibleSources.length === sources.length
        ? d.ventas
        : visibleSources.reduce((acc, s) => acc + (d.fuentes[s]?.ventas || 0), 0);
      return { mes: d.mes, leads, ventas, fuentes: d.fuentes };
    });

  const maxLeads = Math.max(...dataWithFiltered.map((d) => d.leads)) * 1.1 || 1;
  const maxVentas = Math.max(...dataWithFiltered.map((d) => d.ventas)) * 1.1 || 1;

  // Cada mes tiene su slot de ancho fijo
  const slotW = data.length > 0 ? chartW / data.length : chartW;
  const groupPadRatio = 0.25;
  const groupW = slotW * (1 - groupPadRatio);
  const barW = visibleSources.length > 0 ? groupW / visibleSources.length : groupW;
  const groupX0 = (i: number) => padding.left + i * slotW + (slotW - groupW) / 2;
  const barX = (i: number, j: number) => groupX0(i) + j * barW;

  const yLeads = (v: number) => padding.top + chartH - (v / maxLeads) * chartH;
  const yVentas = (v: number) => padding.top + chartH - (v / maxVentas) * chartH;

  // 5 grid lines
  const yTicks = 5;
  const yGrid = Array.from({ length: yTicks + 1 }, (_, i) => {
    const ratio = i / yTicks;
    return {
      leads: Math.round(maxLeads * ratio),
      ventas: Math.round(maxVentas * ratio),
      y: padding.top + chartH - chartH * ratio,
    };
  });

  // Polyline points for ventas (filtradas) â€” a traves del CENTRO de cada grupo
  const ventasPoints = dataWithFiltered
    .map((d, i) => `${groupX0(i) + groupW / 2},${yVentas(d.ventas)}`)
    .join(" ");

  // Titulo dinamico para la leyenda de ventas
  const ventasLabel = visibleSources.length === sources.length
    ? "Ventas total"
    : `Ventas (${visibleSources.join(" + ")})`;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full" style={{ maxWidth: "100%" }}>
      {/* Grid lines */}
      {yGrid.map((g, i) => (
        <g key={`grid-${i}`}>
          <line
            x1={padding.left} y1={g.y} x2={width - padding.right} y2={g.y}
            stroke="#334155" strokeWidth={0.5} strokeDasharray="2,3"
          />
          <text x={padding.left - 8} y={g.y + 3} fill="#94a3b8" fontSize={10} textAnchor="end">
            {g.leads.toLocaleString("es-PY")}
          </text>
        </g>
      ))}

      {/* Y axis labels right (ventas) */}
      {yGrid.map((g, i) => (
        <text key={`vgrid-${i}`} x={width - padding.right + 8} y={g.y + 3} fill="#a3e635" fontSize={10} textAnchor="start">
          {g.ventas.toLocaleString("es-PY")}
        </text>
      ))}

      {/* X axis labels (meses) */}
      {data.map((d, i) => (
        <text
          key={`x-${i}`}
          x={groupX0(i) + groupW / 2} y={height - padding.bottom + 18}
          fill="#94a3b8" fontSize={10} textAnchor="middle"
        >
          {d.mes}
        </text>
      ))}

      {/* Bars: leads por fuente (grouped) */}
      {dataWithFiltered.map((d, i) => (
        <g key={`bars-${i}`}>
          {visibleSources.map((src, j) => {
            const v = d.fuentes[src]?.leads || 0;
            const h = chartH - (yLeads(v) - padding.top);
            const color = FONT_COLORS[src] || DEFAULT_COLOR;
            return (
              <rect
                key={`b-${i}-${src}`}
                x={barX(i, j) + 1}
                y={yLeads(v)}
                width={Math.max(1, barW - 2)}
                height={Math.max(0, h)}
                fill={color}
                opacity={0.75}
              >
                <title>{`${d.mes} · ${src}: ${v.toLocaleString("es-PY")} leads`}</title>
              </rect>
            );
          })}
        </g>
      ))}

      {/* Line: ventas (total o filtradas) â€” a traves del centro de cada grupo */}
      <polyline
        points={ventasPoints}
        fill="none" stroke="#a3e635" strokeWidth={2.5}
      />
      {dataWithFiltered.map((d, i) => (
        <circle
          key={`v-${i}`}
          cx={groupX0(i) + groupW / 2}
          cy={yVentas(d.ventas)}
          r={4} fill="#a3e635"
        >
          <title>{`${d.mes}: ${d.ventas.toLocaleString("es-PY")} ventas`}</title>
        </circle>
      ))}

      {/* Legend */}
      {sources.map((src, idx) => {
        const hidden = hiddenSources.has(src);
        const color = FONT_COLORS[src] || DEFAULT_COLOR;
        return (
          <g key={`leg-${src}`} transform={`translate(${width - padding.right + 30}, ${padding.top + idx * 18})`} opacity={hidden ? 0.35 : 1}>
            <rect x={-4} y={-7} width={8} height={8} fill={color} opacity={0.75} />
            <text x={8} y={0} fill="#cbd5e1" fontSize={11}>{src}</text>
          </g>
        );
      })}
      <g transform={`translate(${width - padding.right + 30}, ${padding.top + sources.length * 18 + 6})`}>
        <line x1={-6} y1={-3} x2={6} y2={-3} stroke="#a3e635" strokeWidth={2.5} />
        <circle cx={0} cy={-3} r={3} fill="#a3e635" />
        <text x={12} y={0} fill="#a3e635" fontSize={11} fontWeight="510">{ventasLabel}</text>
      </g>
    </svg>
  );
}

// â”€â”€ Chart Section Component (reusable per UN) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function ChartSection({
  title,
  subtitle,
  data,
  accentColor,
}: {
  title: string;
  subtitle: string;
  data: EvolucionData;
  accentColor: string;
}) {
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const toggleSource = (src: string) => {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(src)) next.delete(src);
      else next.add(src);
      return next;
    });
  };

  return (
    <div className="bg-graphite border border-charcoal-grey rounded-lg p-6">
      {/* Header con KPIs */}
      <div className="flex items-baseline justify-between mb-4 flex-wrap gap-2">
        <div>
          <h2 className="text-base font-[590] text-porcelain flex items-center gap-2">
            <span className="w-1.5 h-5 rounded" style={{ backgroundColor: accentColor }}></span>
            {title}
          </h2>
          <p className="text-fog-grey text-[11px] mt-0.5">{subtitle}</p>
        </div>
        <div className="flex gap-4 text-[11px]">
          <div>
            <span className="text-fog-grey uppercase tracking-wide mr-1">Leads:</span>
            <span className="text-porcelain font-[510]">{data.totales.leads.toLocaleString("es-PY")}</span>
          </div>
          <div>
            <span className="text-fog-grey uppercase tracking-wide mr-1">Ventas:</span>
            <span className="text-neon-lime font-[510]">{data.totales.ventas.toLocaleString("es-PY")}</span>
          </div>
          <div>
            <span className="text-fog-grey uppercase tracking-wide mr-1">Conv:</span>
            <span className="text-cyan-300 font-[510]">{data.totales.conversion}%</span>
          </div>
        </div>
      </div>

      {/* Toggle chips */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <span className="text-fog-grey text-[11px] uppercase tracking-wide mr-2">Fuentes:</span>
        {data.fuentes.map((src) => {
          const isHidden = hidden.has(src);
          const color = FONT_COLORS[src] || DEFAULT_COLOR;
          return (
            <button
              key={src}
              onClick={() => toggleSource(src)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-[11px] font-[510] transition-all ${
                isHidden
                  ? "bg-deep-slate/50 border-charcoal-grey/50 text-fog-grey line-through"
                  : "bg-deep-slate border-charcoal-grey text-porcelain hover:border-neon-lime/50"
              }`}
              style={{ color: isHidden ? undefined : color }}
            >
              <span
                className="w-2.5 h-2.5 rounded-full"
                style={{ backgroundColor: color, opacity: isHidden ? 0.3 : 1 }}
              />
              {src}
            </button>
          );
        })}
        {hidden.size > 0 && (
          <button
            onClick={() => setHidden(new Set())}
            className="text-[11px] text-fog-grey hover:text-neon-lime ml-2 underline"
          >
            Mostrar todas
          </button>
        )}
      </div>

      <ComboChart data={data.serie_mensual} sources={data.fuentes} hiddenSources={hidden} />
    </div>
  );
}

// â”€â”€ Page â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export default function EvolucionPage() {
  const router = useRouter();
  const [dataTodas, setDataTodas] = useState<EvolucionData | null>(null);
  const [dataODO, setDataODO] = useState<EvolucionData | null>(null);
  const [dataMPP, setDataMPP] = useState<EvolucionData | null>(null);
  const [dataEST, setDataEST] = useState<EvolucionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");

  const fetchAll = async (d?: string, h?: string) => {
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem("token");
      if (!token) { router.push("/"); return; }
      const buildUrl = (eid?: number) => {
        const params = new URLSearchParams();
        if (d) params.append("desde", d);
        if (h) params.append("hasta", h);
        if (eid) params.append("enterprise_id", String(eid));
        return `http://localhost:8000/api/dashboard/evolucion${params.toString() ? "?" + params.toString() : ""}`;
      };
      const headers = { Authorization: `Bearer ${token}` };

      const [r1, r2, r3, r4] = await Promise.all([
        fetch(buildUrl(), { headers }),
        fetch(buildUrl(1), { headers }),  // Odontologia
        fetch(buildUrl(2), { headers }),  // Med. Prepaga
        fetch(buildUrl(5), { headers }),  // Med. Estetica
      ]);
      if (!r1.ok) throw new Error(`HTTP ${r1.status} (todas)`);
      setDataTodas(await r1.json());
      if (r2.ok) setDataODO(await r2.json());
      if (r3.ok) setDataMPP(await r3.json());
      if (r4.ok) setDataEST(await r4.json());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAll();
  }, []);

  const aplicar = () => fetchAll(desde || undefined, hasta || undefined);

  // Quick range presets
  const setRange = (months: number) => {
    const today = new Date();
    const past = new Date(today.getFullYear(), today.getMonth() - months + 1, 1);
    const d = past.toISOString().slice(0, 10);
    const h = today.toISOString().slice(0, 10);
    setDesde(d);
    setHasta(h);
    fetchAll(d, h);
  };

  if (loading && !dataTodas) return <div className="text-porcelain p-8">Cargando...</div>;
  if (error) return <div className="text-warning-red p-8">Error: {error}</div>;
  if (!dataTodas) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-[590] text-porcelain">Evolución Mensual por Unidad de Negocio</h1>
        <p className="text-fog-grey text-sm mt-1">
          Leads y ventas por fuente, medidos individualmente por cada UN
        </p>
      </div>

      {/* Filtros */}
      <div className="bg-graphite border border-charcoal-grey rounded-lg p-4 flex flex-wrap items-end gap-4">
        <div>
          <label className="text-fog-grey text-[11px] block mb-1">Desde</label>
          <input
            type="date"
            value={desde}
            onChange={(e) => setDesde(e.target.value)}
            className="bg-deep-slate border border-charcoal-grey text-porcelain px-3 py-1.5 rounded text-sm"
          />
        </div>
        <div>
          <label className="text-fog-grey text-[11px] block mb-1">Hasta</label>
          <input
            type="date"
            value={hasta}
            onChange={(e) => setHasta(e.target.value)}
            className="bg-deep-slate border border-charcoal-grey text-porcelain px-3 py-1.5 rounded text-sm"
          />
        </div>
        <button
          onClick={aplicar}
          className="bg-neon-lime text-pitch-black px-4 py-1.5 rounded text-sm font-[510] hover:bg-neon-lime/80"
        >
          Aplicar
        </button>
        <div className="flex gap-2 ml-auto">
          <button onClick={() => setRange(3)} className="text-xs text-fog-grey hover:text-porcelain px-2 py-1 border border-charcoal-grey rounded">3M</button>
          <button onClick={() => setRange(6)} className="text-xs text-fog-grey hover:text-porcelain px-2 py-1 border border-charcoal-grey rounded">6M</button>
          <button onClick={() => setRange(12)} className="text-xs text-fog-grey hover:text-porcelain px-2 py-1 border border-charcoal-grey rounded">12M</button>
          <button onClick={() => setRange(24)} className="text-xs text-fog-grey hover:text-porcelain px-2 py-1 border border-charcoal-grey rounded">24M</button>
        </div>
      </div>

      {/* 4 Charts: Todas + cada UN */}
      {dataTodas && (
        <ChartSection
          title="Todas las UN"
          subtitle="Resumen global â€” todas las unidades de negocio"
          data={dataTodas}
          accentColor="#94a3b8"
        />
      )}

      {dataODO && (
        <ChartSection
          title="Odontología"
          subtitle="Unidad de negocio 1 â€” leads y ventas por fuente"
          data={dataODO}
          accentColor="#22d3ee"
        />
      )}

      {dataMPP && (
        <ChartSection
          title="Med. Prepaga"
          subtitle="Unidad de negocio 2 â€” leads y ventas por fuente"
          data={dataMPP}
          accentColor="#fbbf24"
        />
      )}

      {dataEST && (
        <ChartSection
          title="Med. Estética"
          subtitle="Unidad de negocio 5 â€” leads y ventas por fuente"
          data={dataEST}
          accentColor="#a78bfa"
        />
      )}
    </div>
  );
}

