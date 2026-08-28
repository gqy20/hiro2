"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { apiFetch, isMockMode } from "@/lib/api/client";
import type { DatasetOverview } from "@/lib/datasets";
import { formatDate } from "@/lib/time";
import {
  ChartScatter,
  ClipboardText,
  Database,
  FlowArrow,
  Funnel,
  GitDiff,
  Graph,
  MagnifyingGlass,
  ShieldCheck,
} from "@phosphor-icons/react";
import { Tooltip } from "antd";

gsap.registerPlugin(useGSAP);

const navigation = [
  { href: "/", label: "工作台", icon: ChartScatter },
  { href: "/new-jobs", label: "岗位发现", icon: MagnifyingGlass },
  { href: "/positions", label: "我的岗位", icon: GitDiff },
  { href: "/skills", label: "能力全景", icon: Graph },
  { href: "/diagnosis", label: "候选诊断", icon: ClipboardText },
  { href: "/career", label: "求职成长", icon: ChartScatter },
  { href: "/career/jobs", label: "目标岗位", icon: Graph },
  { href: "/profile", label: "我的画像", icon: ClipboardText },
  { href: "/career/path", label: "学习路径", icon: FlowArrow },
];

// 求职成长工作区导航项（/diagnosis 为两区共享，不在排除列）
const CAREER_ONLY_HREFS = new Set([
  "/career",
  "/career/jobs",
  "/career/path",
  "/profile",
]);
const CAREER_NAV_HREFS = new Set([...CAREER_ONLY_HREFS, "/diagnosis"]);

const dataNavigation = [
  { href: "/data", label: "总览", icon: Database },
  { href: "/data/sources", label: "来源", icon: FlowArrow },
  { href: "/data/pipeline", label: "流水线", icon: Funnel },
  { href: "/tasks", label: "审核任务", icon: ClipboardText },
  { href: "/evaluation", label: "评测与质量", icon: ShieldCheck },
  { href: "/temporal", label: "时间情报", icon: ChartScatter },
];

type Workspace = "recruiting" | "career" | "data";
const WORKSPACE_KEY = "hiro2.workspace";

export function AppShell({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const pathname = usePathname();
  // 顶栏“数据截至”取数据集最近更新时间，mock 模式或请求失败时不显示
  const [dataAsOf, setDataAsOf] = useState<string | null>(null);
  useEffect(() => {
    if (isMockMode()) return;
    let cancelled = false;
    apiFetch<DatasetOverview>("/datasets/overview")
      .then((overview) => {
        if (cancelled) return;
        const latest = overview.datasets
          .map((d) => d.updated_at)
          .filter(Boolean)
          .sort()
          .at(-1);
        setDataAsOf(latest ? formatDate(latest).slice(5) : null);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);
  const router = useRouter();
  const [workspace, setWorkspace] = useState<Workspace>(() => {
    const fallback: Workspace =
      pathname.startsWith("/data") ||
      pathname.startsWith("/temporal") ||
      pathname.startsWith("/tasks") ||
      pathname.startsWith("/evaluation") ||
      pathname.startsWith("/quality") ||
      pathname.startsWith("/datasets")
        ? "data"
        : pathname.startsWith("/career") || pathname.startsWith("/profile")
          ? "career"
          : "recruiting";
    if (typeof window === "undefined") return fallback;
    const stored = window.localStorage.getItem(WORKSPACE_KEY);
    if (stored === "recruiting" || stored === "career" || stored === "data") {
      return stored;
    }
    return fallback;
  });
  const careerMode = workspace === "career";
  const dataMode = workspace === "data";
  const visibleNavigation = dataMode
    ? dataNavigation
    : careerMode
      ? navigation.filter((item) => CAREER_NAV_HREFS.has(item.href))
      : navigation.filter((item) => !CAREER_ONLY_HREFS.has(item.href));

  function isActive(href: string): boolean {
    // 精确匹配：避免 /data 在 /data/sources 等子页下误亮（总览不再一直亮）
    return pathname === href;
  }
  const contentRef = useRef<HTMLElement>(null);

  function switchWorkspace(next: Workspace) {
    if (next === workspace) return;
    window.localStorage.setItem(WORKSPACE_KEY, next);
    setWorkspace(next);
    if (next === "career") router.push("/career");
    else if (next === "data") router.push("/data");
    else router.push("/");
  }

  useGSAP(
    () => {
      const target = contentRef.current?.firstElementChild;
      if (!target) return;
      const media = gsap.matchMedia();
      media.add("(prefers-reduced-motion: no-preference)", () => {
        gsap.fromTo(
          target,
          { autoAlpha: 0.94, y: 6 },
          {
            autoAlpha: 1,
            y: 0,
            duration: 0.32,
            ease: "power2.out",
            clearProps: "transform,opacity,visibility",
          },
        );
      });
      return () => media.revert();
    },
    { dependencies: [pathname], scope: contentRef, revertOnUpdate: true },
  );

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        跳到主内容
      </a>
      <header className="topbar">
        <Link className="brand" href="/" aria-label="Hiro2 工作台">
          <span className="brand-mark">H</span>
          <span>HIRO2</span>
        </Link>
        <nav aria-label="主导航" className="main-nav">
          {visibleNavigation.map(({ href, label, icon: Icon }) => (
            <Tooltip key={label} title={label}>
              <Link
                className={
                  isActive(href) ? "nav-link nav-link-active" : "nav-link"
                }
                href={href}
              >
                <Icon
                  aria-hidden
                  size={17}
                  weight={isActive(href) ? "fill" : "regular"}
                />
                <span>{label}</span>
              </Link>
            </Tooltip>
          ))}
        </nav>
        <div className="topbar-meta">
          <div className="workspace-switch" aria-label="切换工作区">
            <button
              aria-pressed={workspace === "recruiting"}
              className={workspace === "recruiting" ? "is-active" : ""}
              onClick={() => switchWorkspace("recruiting")}
              type="button"
            >
              招聘
            </button>
            <button
              aria-pressed={workspace === "career"}
              className={workspace === "career" ? "is-active" : ""}
              onClick={() => switchWorkspace("career")}
              type="button"
            >
              成长
            </button>
            <button
              aria-pressed={workspace === "data"}
              className={workspace === "data" ? "is-active" : ""}
              onClick={() => switchWorkspace("data")}
              type="button"
            >
              数据
            </button>
          </div>
          <span className="live-dot" aria-hidden />
          {dataAsOf ? <span>数据截至 {dataAsOf}</span> : null}
        </div>
      </header>
      <main id="main-content" ref={contentRef}>
        {children}
      </main>
    </div>
  );
}
