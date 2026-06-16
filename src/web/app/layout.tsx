import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";
import { Providers } from "@/lib/providers";
import { NavLinks } from "@/components/NavLinks";

export const metadata: Metadata = {
  title: "TrustClaims",
  description: "Intelligent Claims Processing Platform"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <div className="min-h-screen flex flex-col bg-slate-50">
            <header className="bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 text-white px-6 py-3 flex items-center justify-between shadow-lg">
              <Link href="/dashboard" className="flex items-center gap-2.5 group">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-sky-400 to-indigo-500 flex items-center justify-center shadow-md group-hover:shadow-lg transition-shadow">
                  <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                  </svg>
                </div>
                <span className="font-bold text-lg tracking-tight">TrustClaims</span>
              </Link>
              <NavLinks />
            </header>
            <div className="bg-gradient-to-r from-amber-50 to-amber-100 text-amber-700 text-xs px-6 py-1.5 text-center font-medium border-b border-amber-200">
              ⚠ All data shown is synthetic — this is a proof-of-concept environment.
            </div>
            <main className="flex-1 p-6 max-w-7xl mx-auto w-full">{children}</main>
            <footer className="border-t border-slate-200 bg-white py-4 px-6 text-center text-xs text-slate-400">
              TrustClaims — Intelligent Claims Processing Platform
            </footer>
          </div>
        </Providers>
      </body>
    </html>
  );
}
