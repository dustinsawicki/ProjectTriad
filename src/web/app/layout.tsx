import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";
import { PortalNav } from "@/components/portal-nav";
import { Providers } from "@/lib/providers";

export const metadata: Metadata = {
  title: "Contoso Claims Portal",
  description: "Agentic Claims Processing — FSI PoC"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <div className="relative flex min-h-screen flex-col">
            <header className="sticky top-0 z-30 border-b border-white/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.92),rgba(248,250,252,0.82))] shadow-[0_16px_40px_rgba(16,34,62,0.08)] backdrop-blur-xl">
              <div className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-6 py-4 lg:flex-row lg:items-center lg:justify-between lg:py-5">
                <Link href="/dashboard" className="group inline-flex items-center gap-4 self-start">
                  <span className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/80 bg-[linear-gradient(180deg,#FFFFFF,#ECF2FA)] text-[11px] font-semibold uppercase tracking-[0.24em] text-accent shadow-sm shadow-slate-900/10">
                    CC
                  </span>
                  <span className="block">
                    <span className="block text-lg font-semibold text-navy">Contoso Claims</span>
                    <span className="block text-[11px] uppercase tracking-[0.28em] text-slate-500">
                      Agentic processing command center
                    </span>
                  </span>
                </Link>
                <PortalNav />
              </div>
              <div className="border-t border-white/60 bg-[linear-gradient(90deg,rgba(197,161,90,0.16),rgba(255,255,255,0.62),rgba(220,230,247,0.9))]">
                <div className="mx-auto max-w-7xl px-6 py-2 text-center text-[11px] font-medium uppercase tracking-[0.24em] text-slate-600">
                  Synthetic demonstration data · human review required · standalone claims PoC
                </div>
              </div>
            </header>
            <main className="mx-auto flex w-full max-w-7xl flex-1 px-6 py-8 lg:py-10">{children}</main>
            <footer className="border-t border-white/70 bg-white/70 backdrop-blur">
              <div className="mx-auto flex w-full max-w-7xl flex-col gap-3 px-6 py-5 text-sm text-slate-500 md:flex-row md:items-center md:justify-between">
                <p>
                  <span className="font-medium text-slate-700">Contoso Claims Portal</span> — enterprise claims intake, triage, routing, and settlement visibility.
                </p>
                <p className="text-xs uppercase tracking-[0.24em] text-slate-400">Built for claims processing proof of concept review</p>
              </div>
            </footer>
          </div>
        </Providers>
      </body>
    </html>
  );
}
