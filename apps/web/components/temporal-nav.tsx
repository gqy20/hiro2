"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const tabs: Array<{ href: string; label: string }> = [
  { href: "/temporal/signals", label: "1. 市场信号" },
  { href: "/temporal/timeline", label: "2. 技术传导" },
  { href: "/temporal/forecasts", label: "3. 趋势预测" },
  { href: "/temporal/suggestions", label: "4. 岗位影响" },
  { href: "/temporal/retrospect", label: "5. 预测复盘" },
];

export function TemporalNav() {
  const pathname = usePathname();
  const current = tabs.find(
    (tab) => pathname === tab.href || pathname?.startsWith(`${tab.href}/`),
  );
  return (
    <>
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
      <h1 className="sr-only">
        {current?.label.replace(/^\d+\.\s*/, "") ?? "时间情报"}
      </h1>
    </>
  );
}
