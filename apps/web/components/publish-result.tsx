import Link from "next/link";
import {
  ArrowLeft,
  ClipboardText,
  GraduationCap,
  Graph,
} from "@phosphor-icons/react";
import { Button, Result, Tag } from "antd";

import { AppShell } from "@/components/app-shell";
import { TrainingOutputSection } from "@/components/training-output-section";

type PublishResultViewProps = {
  jobTitle: string;
  targetVersion: string;
  publishedAt: string;
  versionId?: string;
  reviewCounts: { accepted: number; rejected: number; pending: number };
  onBack: () => void;
};

export function PublishResultView({
  jobTitle,
  targetVersion,
  publishedAt,
  versionId,
  reviewCounts,
  onBack,
}: PublishResultViewProps) {
  return (
    <AppShell>
      <section
        className="publish-result"
        aria-labelledby="publish-result-title"
      >
        <div className="page-heading">
          <div className="title-with-meta">
            <h1 id="publish-result-title">岗位版本已发布</h1>
            <span className="page-meta">
              {`${jobTitle} · ${targetVersion} · ${publishedAt}`}
            </span>
          </div>
          <Tag color="green">已发布</Tag>
        </div>

        <Result
          status="success"
          title={`${targetVersion} 已发布`}
          subTitle="已发布岗位版本不可修改；如需修订请创建新版本。"
          extra={
            <div className="publish-next-actions">
              <span className="publish-next-actions-label">现在可以</span>
              <Link href="/skills">
                <Button icon={<Graph aria-hidden size={15} />}>
                  查看能力图谱
                </Button>
              </Link>
              <Link href="/diagnosis">
                <Button icon={<ClipboardText aria-hidden size={15} />}>
                  诊断候选人
                </Button>
              </Link>
              {versionId ? (
                <a href="#training-output">
                  <Button icon={<GraduationCap aria-hidden size={15} />}>
                    查看培养任务
                  </Button>
                </a>
              ) : null}
              <Button
                icon={<ArrowLeft aria-hidden size={15} />}
                onClick={onBack}
              >
                返回岗位更新
              </Button>
            </div>
          }
        />

        <section
          className="review-summary"
          aria-labelledby="review-summary-title"
        >
          <h2 id="review-summary-title">本次审核记录</h2>
          <dl>
            <div>
              <dt>已接受</dt>
              <dd>{reviewCounts.accepted}</dd>
            </div>
            <div>
              <dt>已拒绝</dt>
              <dd>{reviewCounts.rejected}</dd>
            </div>
            <div>
              <dt>待确认</dt>
              <dd>{reviewCounts.pending}</dd>
            </div>
          </dl>
        </section>

        {versionId ? (
          <div id="training-output">
            <TrainingOutputSection versionId={versionId} />
          </div>
        ) : null}
      </section>
    </AppShell>
  );
}
