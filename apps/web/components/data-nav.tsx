"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  { href: "/data", label: "总览" },
  { href: "/data/sources", label: "来源" },
  { href: "/data/pipeline", label: "流水线" },
  { href: "/data/quality", label: "质量" },
] as const;

export function DataNav() {
  const pathname = usePathname();
  return (
    <nav aria-label="数据工作区" className="data-subnav">
      {items.map(({ href, label }) => {
        const active =
          href === "/data"
            ? pathname === "/data"
            : pathname.startsWith(href);
        return (
          <Link
            key={href}
            aria-current={active ? "page" : undefined}
            className={active ? "data-subnav-link is-active" : "data-subnav-link"}
            href={href}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
