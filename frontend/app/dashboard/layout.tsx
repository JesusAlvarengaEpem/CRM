"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Home", icon: "⌂" },
  { href: "/dashboard/actividad", label: "Actividad", icon: "⏳" },
  { href: "/dashboard/leads", label: "Leads", icon: "📋" },
  { href: "/dashboard/resumen", label: "Resumen", icon: "📊" },
  { href: "/dashboard/evolucion", label: "Evolución", icon: "↗" },
  { href: "/dashboard/metricas", label: "Métricas", icon: "⊡" },
  { href: "/dashboard/funnel", label: "Funnel", icon: "⧩" },
  { href: "/dashboard/pipeline", label: "Pipeline", icon: "↯" },
  { href: "/dashboard/vendedores", label: "Vendedores", icon: "◈" },
  { href: "/dashboard/asignacion", label: "Asignación", icon: "◉" },
  { href: "/dashboard/supervisores", label: "Supervisores", icon: "◎" },
  { href: "/dashboard/campanas", label: "Campañas", icon: "⛭" },
  // { href: "/dashboard/fuentes", label: "Comparación Fuentes", icon: "⚖" },  // DEPRECATED — reemplazado por Actividad + Sync ThinkChat
  // { href: "/dashboard/lead", label: "Lead Track", icon: "⨂" },              // DEPRECATED — reemplazado por Actividad (click en evento → lead)
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<{ fullname: string; role: string } | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) { router.push("/"); return; }
    try {
      const payload = JSON.parse(atob(token.split(".")[1]));
      setUser({ fullname: payload.fullname, role: payload.role });
    } catch {}
  }, []);

  const logout = () => {
    localStorage.removeItem("token");
    router.push("/");
  };

  return (
    <div className="min-h-screen bg-pitch-black flex">
      {/* Sidebar */}
      <aside className="w-56 bg-graphite border-r border-charcoal-grey flex flex-col shrink-0 min-h-screen">
        {/* Logo */}
        <div className="px-5 py-5 border-b border-charcoal-grey">
          <h1 className="text-neon-lime font-[590] text-sm tracking-[-0.13px]">Midnight Command Center</h1>
          <p className="text-fog-grey text-[11px] mt-0.5">CRM EPEM</p>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-0.5">
          {NAV_ITEMS.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                  active
                    ? "bg-deep-slate text-neon-lime font-[510]"
                    : "text-storm-cloud hover:text-porcelain hover:bg-deep-slate/50"
                }`}
              >
                <span className="text-xs w-4 text-center">{item.icon}</span>
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* User */}
        {user && (
          <div className="px-5 py-4 border-t border-charcoal-grey">
            <p className="text-light-steel text-xs font-[510]">{user.fullname}</p>
            <p className="text-fog-grey text-[11px]">{user.role}</p>
            <button onClick={logout} className="text-fog-grey hover:text-warning-red text-[11px] mt-2 transition-colors">
              Cerrar sesión
            </button>
          </div>
        )}
      </aside>

      {/* Main content */}
      <main className="flex-1 p-8 min-w-0">{children}</main>
    </div>
  );
}
