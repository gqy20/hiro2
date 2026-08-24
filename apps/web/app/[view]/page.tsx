import { Empty } from "antd";

import { AppShell } from "@/components/app-shell";

const views: Record<string, string> = {
  diagnosis: "人岗诊断",
  evaluation: "评测中心",
  "new-jobs": "新岗位",
  skills: "技能图谱",
};

export default async function PendingPage({
  params,
}: Readonly<{ params: Promise<{ view: string }> }>) {
  const { view } = await params;
  const title = views[view] ?? "工作台";

  return (
    <AppShell>
      <section className="pending-page" aria-labelledby="pending-title">
        <div>
          <p className="route-label">模块建设中</p>
          <h1 id="pending-title">{title}</h1>
        </div>
        <Empty description="该模块将在岗位更新闭环稳定后接入。" />
      </section>
    </AppShell>
  );
}
