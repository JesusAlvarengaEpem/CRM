import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CRM EPEM — Midnight Command Center",
  description: "Dashboard de CRM unificado — Botmaker + Manual",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es" className="dark">
      <body className="bg-pitch-black text-porcelain antialiased min-h-screen">
        {children}
      </body>
    </html>
  );
}
