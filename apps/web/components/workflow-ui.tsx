import { Alert, Empty, Skeleton } from "antd";
import type { ReactNode } from "react";

import type { ReviewStatus } from "@/lib/job-update";

export function FixtureState({
  state,
  emptyText = "暂无数据。",
  errorText = "数据暂时不可用。",
  action,
}: {
  state: "loading" | "empty" | "error";
  emptyText?: string;
  errorText?: string;
  action?: ReactNode;
}) {
  if (state === "loading")
    return (
      <section className="fixture-state">
        <Skeleton active paragraph={{ rows: 4 }} />
      </section>
    );
  if (state === "error")
    return (
      <section className="fixture-state">
        <Alert description={errorText} showIcon title="加载失败" type="error" />
        {action}
      </section>
    );
  return (
    <section className="fixture-state">
      <Empty description={emptyText} />
      {action}
    </section>
  );
}

export function SectionHeader({
  title,
  meta,
  action,
}: {
  title: string;
  meta?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="section-heading">
      <div className="inline-heading">
        <h2>{title}</h2>
        {meta ? <span>{meta}</span> : null}
      </div>
      {action}
    </div>
  );
}

export function skillStatusToReview(
  status: "ready" | "partial" | "missing",
): ReviewStatus {
  return status === "ready"
    ? "accepted"
    : status === "missing"
      ? "needs_evidence"
      : "reviewing";
}
