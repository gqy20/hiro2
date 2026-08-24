# ADR 0003：预测与岗位发布边界

## 背景

日报和 RSS 提供技术先导信号，但不能单独证明企业岗位需求。

## 决定

时间情报系统只输出 `JobImpactSuggestion`。岗位系统结合 JD、专家基线和证据后，通过人工审核创建新的 `PublishedJobVersion`。

## 后果

预测错误不会直接影响正式岗位图谱或候选人匹配结论。

## 替代方案

不允许 ForecastEngine、LLM 或 RSS 任务直接修改岗位版本。
