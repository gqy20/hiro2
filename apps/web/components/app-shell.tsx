"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
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
  GitDiff,
  Graph,
  MagnifyingGlass,
  Question,
  ShieldCheck,
} from "@phosphor-icons/react";
import { Tooltip } from "antd";

import { OnboardingTour } from "@/components/onboarding-tour";

gsap.registerPlugin(useGSAP);

const recruitingNavigation = [
  { href: "/", label: "工作台", icon: ChartScatter },
  { href: "/new-jobs", label: "岗位发现", icon: MagnifyingGlass },
  { href: "/positions", label: "我的岗位", icon: GitDiff },
  { href: "/skills", label: "能力全景", icon: Graph },
  { href: "/diagnosis", label: "候选诊断", icon: ClipboardText },
];

const careerNavigation = [
  { href: "/career/jobs", label: "目标岗位", icon: Graph },
  { href: "/profile", label: "我的画像", icon: ClipboardText },
  { href: "/career/diagnosis", label: "人岗诊断", icon: ClipboardText },
  { href: "/career/path", label: "学习路径", icon: FlowArrow },
  { href: "/career/resume", label: "简历工作台", icon: ClipboardText },
];

const dataNavigation = [
  { href: "/data", label: "总览", icon: Database },
  { href: "/data/assets", label: "数据资产", icon: FlowArrow },
  { href: "/tasks", label: "证据审核", icon: ClipboardText },
  { href: "/evaluation", label: "评测质量", icon: ShieldCheck },
  { href: "/temporal", label: "趋势洞察", icon: ChartScatter },
];

type Workspace = "recruiting" | "career" | "data";

function workspaceForPath(pathname: string): Workspace {
  if (
    pathname.startsWith("/data") ||
    pathname.startsWith("/temporal") ||
    pathname.startsWith("/tasks") ||
    pathname.startsWith("/evaluation")
  )
    return "data";
  if (pathname.startsWith("/career") || pathname.startsWith("/profile"))
    return "career";
  return "recruiting";
}

export function AppShell({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const pathname = usePathname();
  const workspace = workspaceForPath(pathname);
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
  const careerMode = workspace === "career";
  const dataMode = workspace === "data";
  const visibleNavigation = dataMode
    ? dataNavigation
    : careerMode
      ? careerNavigation
      : recruitingNavigation;

  function isActive(href: string): boolean {
    // 精确匹配：避免 /data 在 /data/assets 等子页下误亮。
    if (href === "/data/assets") {
      return pathname === href || pathname.startsWith(`${href}/`);
    }
    return pathname === href;
  }
  const contentRef = useRef<HTMLElement>(null);
  const [tourOpen, setTourOpen] = useState(false);

  // 首访每个工作区时自动弹一次引导；localStorage 记忆已读，之后用问号重开。
  // 延迟 600ms 等首屏渲染与锚点就绪。
  // 注意：e2e 由共享 fixture（tests/e2e/fixture.ts）预置已读标记跳过，
  // 产品代码不为测试写守卫。
  useEffect(() => {
    const key = `hiro2:tour-seen:${workspace}`;
    if (localStorage.getItem(key)) return;
    const timer = window.setTimeout(() => setTourOpen(true), 600);
    return () => window.clearTimeout(timer);
  }, [workspace]);

  function closeTour() {
    setTourOpen(false);
    try {
      localStorage.setItem(`hiro2:tour-seen:${workspace}`, "1");
    } catch {
      // 隐私模式等存储不可用时静默降级，引导仍只随本次会话出现一次
    }
  }

  function switchWorkspace(next: Workspace) {
    if (next === workspace) return;
    if (next === "career") router.push("/career/jobs");
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
        <Link className="brand" href="/" aria-label="hiro 工作台">
          <Image
            className="brand-mark"
            src="/hiro-mark.svg"
            alt=""
            aria-hidden="true"
            width={28}
            height={28}
            priority
          />
          <span className="brand-wordmark">hiro</span>
        </Link>
        <nav aria-label="主导航" className="main-nav">
          {visibleNavigation.map(({ href, label, icon: Icon }) => (
            <Tooltip key={label} title={label}>
              <Link
                className={
                  isActive(href) ? "nav-link nav-link-active" : "nav-link"
                }
                data-tour={href}
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
              求职
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
          <Tooltip title="使用引导">
            <button
              aria-label="使用引导"
              className="help-trigger"
              onClick={() => setTourOpen(true)}
              type="button"
            >
              <Question aria-hidden size={16} />
            </button>
          </Tooltip>
          <span className="live-dot" aria-hidden />
          {dataAsOf ? <span>数据截至 {dataAsOf}</span> : null}
        </div>
      </header>
      <main id="main-content" ref={contentRef}>
        {children}
      </main>
      <OnboardingTour
        onClose={closeTour}
        open={tourOpen}
        workspace={workspace}
      />
    </div>
  );
}
