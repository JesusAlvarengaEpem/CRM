"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();
  const [email, setEmail] = useState("admin@epem.com");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const res = await fetch("http://localhost:8000/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) throw new Error("Credenciales inválidas");

      const data = await res.json();
      localStorage.setItem("token", data.access_token);
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message || "Error de conexión");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-pitch-black flex items-center justify-center p-6">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <img
            src="/logo-epem.png"
            alt="Grupo EPEM"
            className="h-16 mx-auto mb-4"
          />
          <h1 className="font-[590] text-2xl text-porcelain tracking-[-0.22px]">
            CRM Unificado
          </h1>
          <p className="text-storm-cloud text-sm mt-2">
            Midnight Command Center
          </p>
        </div>

        {/* Login Card */}
        <form onSubmit={handleLogin}>
          <div className="bg-graphite rounded-md shadow-[rgba(0,0,0,0.4)_0px_2px_4px_0px] p-6">
            <div className="space-y-4">
              <div>
                <label className="block text-storm-cloud text-xs font-medium mb-1.5">
                  Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-pitch-black border border-charcoal-grey rounded-md px-3.5 py-3 text-porcelain text-sm placeholder:text-fog-grey focus:outline-none focus:border-neon-lime transition-colors"
                />
              </div>
              <div>
                <label className="block text-storm-cloud text-xs font-medium mb-1.5">
                  Contraseña
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-pitch-black border border-charcoal-grey rounded-md px-3.5 py-3 text-porcelain text-sm placeholder:text-fog-grey focus:outline-none focus:border-neon-lime transition-colors"
                />
              </div>

              {error && (
                <p className="text-warning-red text-xs">{error}</p>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-neon-lime text-pitch-black font-[590] text-sm rounded-md py-3 hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {loading ? "Ingresando..." : "Ingresar"}
              </button>
            </div>
          </div>
        </form>

        {/* Status */}
        <div className="mt-6 text-center">
          <p className="text-fog-grey text-xs">
            FastAPI <span className="text-emerald">✓</span> operativo
            {" · "}
            PostgreSQL <span className="text-emerald">✓</span> conectado
          </p>
        </div>
      </div>
    </main>
  );
}

