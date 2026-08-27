"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import {
  ChartScatter,
  ClipboardText,
  FileText,
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
  { href: "/resumes", label: "简历解析", icon: FileText },
  { href: "/diagnosis", label: "候选诊断", icon: ClipboardText },
  { href: "/evaluation", label: "评测中心", icon: ShieldCheck },
  { href: "/career", label: "求职成长", icon: ChartScatter },
  { href: "/profile", label: "我的画像", icon: ClipboardText },
];

type Workspace = "recruiting" | "career";
const WORKSPACE_KEY = "hiro2.workspace";

export function AppShell({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const pathname = usePathname();
  const router = useRouter();
  const [workspace, setWorkspace] = useState<Workspace>(() => {
    const fallback = pathname.startsWith("/career") || pathname.startsWith("/profile")
      ? "career"
      : "recruiting";
    if (typeof window === "undefined") return fallback;
    const stored = window.localStorage.getItem(WORKSPACE_KEY);
    return stored === "career" || stored === "recruiting" ? stored : fallback;
  });
  const careerMode = workspace === "career";
  const visibleNavigation = careerMode
    ? navigation.filter((item) => ["/career", "/profile", "/diagnosis"].includes(item.href))
    : navigation.filter((item) => !["/career", "/profile"].includes(item.href));
  const contentRef = useRef<HTMLElement>(null);

  function switchWorkspace(next: Workspace) {
    if (next === workspace) return;
    window.localStorage.setItem(WORKSPACE_KEY, next);
    setWorkspace(next);
    router.push(next === "career" ? "/career" : "/");
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
                  pathname === href ? "nav-link nav-link-active" : "nav-link"
                }
                href={href}
              >
                <Icon
                  aria-hidden
                  size={17}
                  weight={pathname === href ? "fill" : "regular"}
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
          </div>
          <span className="live-dot" aria-hidden />
          <span>数据截至 08-22</span>
        </div>
      </header>
      <main id="main-content" ref={contentRef}>{children}</main>
    </div>
  );
}
