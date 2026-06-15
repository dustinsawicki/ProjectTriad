import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";
import { Providers } from "@/lib/providers";

export const metadata: Metadata = {
  title: "Claims PoC",
  description: "Agentic Claims Processing — FSI PoC"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <div className="min-h-screen flex flex-col">
            <header className="bg-navy text-white px-6 py-3 flex items-center justify-between shadow">
              <Link href="/claims" className="font-bold text-lg tracking-tight">
                Contoso Claims <span className="text-ice font-normal text-sm">/ Agentic PoC</span>
              </Link>
              <nav className="flex gap-6 text-sm">
                <Link href="/claims" className="hover:text-ice">Queue</Link>
                <Link href="/audit"  className="hover:text-ice">Audit</Link>
              </nav>
            </header>
            <div className="bg-amber-100 text-amber-900 text-xs px-6 py-1 text-center">
              All data shown is synthetic — this is a proof of concept and not production-ready.
            </div>
            <main className="flex-1 p-6 max-w-7xl mx-auto w-full">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
