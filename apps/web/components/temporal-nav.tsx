"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const tabs: Array<{ href: string; label: string }> = [
  { href: "/temporal/signals", label: "信号流" },
  { href: "/temporal/forecasts", label: "趋势回测" },
  { href: "/temporal/retrospect", label: "预测复盘" },
  { href: "/temporal/suggestions", label: "影响建议" },
];

export function TemporalNav() {
  const pathname = usePathname();
  return (
    <nav aria-label="时间情报" className="temporal-nav">
      {tabs.map((tab) => {
        const active =
          pathname === tab.href || pathname?.startsWith(`${tab.href}/`);
        return (
          <Link
            aria-current={active ? "page" : undefined}
            className={`temporal-nav-tab ${active ? "is-active" : ""}`}
            href={tab.href}
            key={tab.href}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
