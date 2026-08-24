"use client";

import { CheckCircle, XCircle } from "@phosphor-icons/react";
import { Button, Tooltip } from "antd";

import type { ReviewStatus } from "@/lib/job-update";

export const reviewLabels: Record<ReviewStatus, string> = {
  accepted: "已接受",
  needs_evidence: "待确认",
  rejected: "已拒绝",
  reviewing: "待审",
};

export function StatusMark({ status }: { status: ReviewStatus }) {
  const icon =
    status === "accepted" ? (
      <CheckCircle aria-hidden weight="fill" />
    ) : status === "rejected" ? (
      <XCircle aria-hidden weight="fill" />
    ) : (
      <i aria-hidden />
    );
  return (
    <span className={`status-mark status-mark-${status}`}>
      {icon}
      <span>{reviewLabels[status]}</span>
    </span>
  );
}

export function ConfidenceMeter({
  confidence,
  variant = "compact",
}: {
  confidence: number;
  variant?: "compact" | "prominent";
}) {
  const percent = Math.round(confidence * 100);
  return (
    <span
      className={`${variant === "prominent" ? "confidence-meter confidence-meter-prominent" : "confidence-meter"}${confidence < 0.8 ? " confidence-meter-caution" : ""}`}
      aria-label={`${percent}% 置信`}
    >
      <b>{`${percent}%`}</b>
      <i aria-hidden>
        <u style={{ width: `${percent}%` }} />
      </i>
      <em>置信</em>
    </span>
  );
}

export function ReviewActions({
  label,
  onAccept,
  onReject,
}: {
  label: string;
  onAccept: () => void;
  onReject: () => void;
}) {
  return (
    <span className="review-actions" aria-label="审核动作">
      <Tooltip title="接受变化">
        <Button
          aria-label={`接受 ${label}`}
          className="review-action review-action-accept"
          icon={<CheckCircle size={16} />}
          onClick={onAccept}
          size="small"
          type="text"
        />
      </Tooltip>
      <Tooltip title="拒绝变化">
        <Button
          aria-label={`拒绝 ${label}`}
          className="review-action review-action-reject"
          icon={<XCircle size={16} />}
          onClick={onReject}
          size="small"
          type="text"
        />
      </Tooltip>
    </span>
  );
}
