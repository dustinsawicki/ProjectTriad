"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/claims", label: "Claims" },
  { href: "/audit", label: "Audit" },
  { href: "/supervisor", label: "Supervisor" },
];

export function NavLinks() {
  const pathname = usePathname();
  return (
    <nav className="flex gap-1 text-sm">
      {links.map(({ href, label }) => {
        const active = pathname === href || pathname.startsWith(href + "/");
        return (
          <Link key={href} href={href}
            className={`px-3 py-1.5 rounded-lg transition-colors ${
              active
                ? "bg-white/15 text-white font-medium"
                : "text-slate-300 hover:text-white hover:bg-white/10"
            }`}>
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
