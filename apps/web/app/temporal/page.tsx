import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { loadTemporalFixture } from "@/lib/temporal-fixture";

const cards = [
  {
    href: "/temporal/signals",
    title: "信号流 + 信号簇",
    desc: "从日报、招聘、岗位需求中提取的实时信号，按 entity_type 聚类。",
    icon: (
      <svg aria-hidden height="20" viewBox="0 0 24 24" width="20">
        <circle
          cx="11"
          cy="11"
          fill="none"
          r="7"
          stroke="currentColor"
          strokeWidth="2"
        />
        <path d="m16 16 4 4" stroke="currentColor" strokeWidth="2" />
      </svg>
    ),
  },
  {
    href: "/temporal/forecasts",
    title: "趋势回测与当前趋势",
    desc: "30/60/90 天回测命中率 + 当前预测趋势。",
    icon: (
      <svg aria-hidden height="20" viewBox="0 0 24 24" width="20">
        <path
          d="M3 20h18M5 17l5-7 4 5 5-9"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        />
      </svg>
    ),
  },
  {
    href: "/temporal/timeline",
    title: "四层时间轴",
    desc: "论文 arXiv → 生态包 → 媒体传播 → 岗位需求 的技术传导。",
    icon: (
      <svg aria-hidden height="20" viewBox="0 0 24 24" width="20">
        <path
          d="M4 6h16M4 12h10M4 18h6"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        />
      </svg>
    ),
  },
  {
    href: "/temporal/retrospect",
    title: "预测复盘",
    desc: "命中、错判、支持/反证证据与评分。",
    icon: (
      <svg aria-hidden height="20" viewBox="0 0 24 24" width="20">
        <path
          d="M3 12a9 9 0 1 0 3-6.7M3 4v5h5"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        />
      </svg>
    ),
  },
  {
    href: "/temporal/suggestions",
    title: "影响建议（JobImpactSuggestion）",
    desc: "预测建议可进入岗位审核，不直接发布版本。",
    icon: (
      <svg aria-hidden height="20" viewBox="0 0 24 24" width="20">
        <path
          d="M12 2 2 21h20Zm0 7v5m0 3v.01"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        />
      </svg>
    ),
  },
];

export default async function TemporalIndexPage() {
  const fixture = await loadTemporalFixture();
  const pendingSuggestions = fixture.suggestions.filter(
    (s) => s.review_status === "PENDING",
  ).length;
  return (
    <AppShell>
      <section
        className="temporal-index"
        aria-labelledby="temporal-index-title"
      >
        <header className="page-heading">
          <h1 id="temporal-index-title">时间情报</h1>
          <p>
            {`市场信号 → 证据 → 岗位候选/岗位版本 → 审核 → 图谱 → 候选人缺口 → 学习路径`}
          </p>
        </header>
        <ul className="temporal-index-grid">
          {cards.map(({ href, icon, title, desc }) => (
            <li key={href}>
              <Link className="temporal-card" href={href}>
                {icon}
                <span className="temporal-card-title">{title}</span>
                <span className="temporal-card-desc">{desc}</span>
              </Link>
            </li>
          ))}
        </ul>
        <p className="temporal-index-meta">
          {`当前有 ${pendingSuggestions} 条待审核影响建议；3 个 horizon 回测结果（30/60/90 天）已就绪。`}
        </p>
      </section>
    </AppShell>
  );
}
