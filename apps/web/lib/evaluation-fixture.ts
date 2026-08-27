import type { EvaluationOverview } from "@/lib/evaluation";

export async function loadEvaluationFixture(): Promise<EvaluationOverview> {
  return {
    run: {
      id: "RUN-0825-001",
      algorithmVersion: "match-v0.1",
      datasetVersion: "2026-08-25",
      status: "REVIEWING",
    },
    datasets: [
      {
        id: "ds-a",
        name: "JD-AI 应用工程师 30",
        samples: 30,
        jobVersion: "v1.5",
      },
      {
        id: "ds-b",
        name: "JD-AI 应用工程师 22",
        samples: 22,
        jobVersion: "v1.4",
      },
      {
        id: "ds-c",
        name: "日报事实抽取 697",
        samples: 697,
        jobVersion: "temporal-v1",
      },
      {
        id: "ds-d",
        name: "回测 8 月",
        samples: 31,
        jobVersion: "backtest-2026-08",
      },
    ],
    metrics: [
      { key: "precision", label: "命中率", value: 0.61 },
      { key: "recall", label: "召回率", value: 0.74 },
      { key: "confidence", label: "置信度", value: 0.84 },
    ],
    errors: [],
    pending: {
      title: "回测待复盘",
      description: "当前为离线评测快照",
      href: "/tasks",
    },
  };
}
