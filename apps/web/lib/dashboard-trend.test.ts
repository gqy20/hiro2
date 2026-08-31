import { describe, expect, it } from "vitest";

import { smoothSeries } from "../components/dashboard-trend";

describe("smoothSeries（样本加权移动平均）", () => {
  it("压制小样本毛刺：孤立 100% 尖峰被邻域拉低", () => {
    const values = [0, 0, 100, 0, 0];
    const weights = [10, 10, 3, 10, 10];
    const smoothed = smoothSeries(values, weights);
    expect(smoothed[2]).toBeLessThan(30);
    expect(smoothed[2]).toBeGreaterThan(0);
  });

  it("大样本邻域主导平滑结果", () => {
    const values = [10, 10, 50, 10, 10];
    const weights = [1, 1, 10000, 1, 1];
    const smoothed = smoothSeries(values, weights);
    // 中心月样本极大，平滑值贴近中心原值
    expect(smoothed[2]).toBeGreaterThan(45);
  });

  it("边界月份退化为可用窗口平均", () => {
    const values = [20, 40];
    const weights = [4, 9];
    const smoothed = smoothSeries(values, weights);
    expect(smoothed).toHaveLength(2);
    for (const v of smoothed) {
      expect(v).toBeGreaterThanOrEqual(20);
      expect(v).toBeLessThanOrEqual(40);
    }
  });

  it("权重缺失按 1 处理且不产生 NaN", () => {
    const smoothed = smoothSeries([10, 20, 30], []);
    expect(smoothed.every((v) => Number.isFinite(v))).toBe(true);
  });
});
