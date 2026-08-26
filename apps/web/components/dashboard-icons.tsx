"use client";

import { ClipboardText, GitDiff, MagnifyingGlass } from "@phosphor-icons/react";

export function DashboardIcon({ kind, size = 18 }: { kind: "search" | "diff" | "diagnosis"; size?: number }) {
  const Icon = kind === "search" ? MagnifyingGlass : kind === "diff" ? GitDiff : ClipboardText;
  return <Icon aria-hidden size={size} />;
}
