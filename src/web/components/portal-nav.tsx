"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/claims", label: "Claims Queue" },
  { href: "/audit", label: "Audit Log" }
];

export function PortalNav() {
  const pathname = usePathname();

  return (
    <nav className="flex flex-wrap items-center gap-2 rounded-full border border-slate-200/70 bg-white/75 p-1.5 shadow-sm shadow-slate-900/5 backdrop-blur">
      {NAV_ITEMS.map((item) => {
        const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);

        return (
          <Link
            key={item.href}
            href={item.href}
            className={[
              "rounded-full px-4 py-2 text-sm font-medium transition",
              isActive
                ? "bg-navy text-white shadow-sm shadow-navy/20"
                : "text-slate-600 hover:bg-slate-100 hover:text-navy"
            ].join(" ")}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
